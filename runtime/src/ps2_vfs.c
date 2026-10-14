#ifndef _WIN32
#define _FILE_OFFSET_BITS 64
#endif
#include "ps2_runtime.h"
#include "ps2_hle.h"
#include "ps2_vfs.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <dirent.h>
#include <pthread.h>

#define SECTOR        PS2_VFS_SECTOR
#define FIRST_LSN     32u

typedef enum { SRC_IMAGE, SRC_TREE, SRC_HOST } vfs_src;

typedef struct vfs_claim vfs_claim;

typedef struct {
    ps2_disc_file f;
    vfs_src src;
    u64 image_off;
    char *host;
    u32 disc_size;
    const vfs_claim *claim;
    int failed;
} vfs_node;

static vfs_node **nodes;
static u32 nnodes, cnodes;
static u32 *slots;
static u32 nslots;
static int vfs_is_tree, vfs_opened;
static char vfs_path[1024];
static FILE *image_fp;
static u32 end_lsn;
static pthread_mutex_t vfs_lock = PTHREAD_MUTEX_INITIALIZER;
static u64 reads_sectors, reads_bytes, reads_from_mods;

typedef enum { CL_PENDING, CL_DISC, CL_NEW, CL_BAD } claim_kind;

struct vfs_claim {
    char *path;
    char *host;
    u64 size;
    int priority;
    unsigned order;
    const char *owner;
    claim_kind kind;
    u32 won;
};

static vfs_claim **claims;
static u32 nclaims, cclaims;
static u32 nconflicts;

static u32 sectors_of(u32 size) { return size ? (size + SECTOR - 1u) / SECTOR : 1u; }

static char upc(char c) { return (c >= 'a' && c <= 'z') ? (char)(c - 32) : c; }

static int ieq(const char *a, const char *b) {
    while (*a && *b && upc(*a) == upc(*b)) { a++; b++; }
    return !*a && !*b;
}

static int icmp(const char *a, const char *b) {
    while (*a && *b && upc(*a) == upc(*b)) { a++; b++; }
    return (unsigned char)upc(*a) - (unsigned char)upc(*b);
}

static char *xstrdup(const char *s) {
    size_t n = strlen(s) + 1;
    char *d = (char *)malloc(n);
    if (!d) ps2_fatal("vfs: out of memory");
    memcpy(d, s, n);
    return d;
}

static int norm_path(const char *name, char *out, size_t cap) {
    const char *p = name;
    size_t n = 0;
    for (const char *q = p; *q && (q - p) < 16; q++) {
        if (*q == '/' || *q == '\\') break;
        if (*q == ':') { p = q + 1; break; }
    }
    for (; *p; p++) {
        char c = *p == '\\' ? '/' : *p;
        if (c == ';') break;
        if (c == '/' && (n == 0 || out[n - 1] == '/')) continue;
        if (n + 1 >= cap) return -1;
        out[n++] = c;
    }
    while (n && out[n - 1] == '/') n--;
    out[n] = 0;
    return (int)n;
}

#ifdef _WIN32
static int seek64(FILE *fp, u64 off) { return _fseeki64(fp, (long long)off, SEEK_SET); }
#else
static int seek64(FILE *fp, u64 off) { return fseeko(fp, (off_t)off, SEEK_SET); }
#endif

static int host_stat(const char *path, u64 *size, int *is_dir) {
#ifdef _WIN32
    struct _stat64 st;
    if (_stat64(path, &st) != 0) return -1;
#else
    struct stat st;
    if (stat(path, &st) != 0) return -1;
#endif
    if (size) *size = (u64)st.st_size;
    if (is_dir) *is_dir = S_ISDIR(st.st_mode);
    return 0;
}

#define VFS_HANDLES 8
static struct { const char *path; FILE *fp; u64 tick; } handles[VFS_HANDLES];
static u64 handle_tick;

static FILE *handle_for(const char *path) {
    unsigned i, victim = 0;
    for (i = 0; i < VFS_HANDLES; i++) {
        if (handles[i].fp && handles[i].path == path) {
            handles[i].tick = ++handle_tick;
            return handles[i].fp;
        }
    }
    for (i = 0; i < VFS_HANDLES; i++) {
        if (!handles[i].fp) { victim = i; break; }
        if (handles[i].tick < handles[victim].tick) victim = i;
    }
    if (handles[victim].fp) fclose(handles[victim].fp);
    handles[victim].fp = fopen(path, "rb");
    handles[victim].path = handles[victim].fp ? path : NULL;
    handles[victim].tick = ++handle_tick;
    return handles[victim].fp;
}

static void guest_put(u32 addr, const u8 *src, u32 n) {
    while (n) {
        u32 off = addr & PS2_PAGE_MASK;
        u32 chunk = PS2_PAGE_SIZE - off;
        u8 *p = ps2_pt[addr >> PS2_PAGE_BITS];
        if (chunk > n) chunk = n;
        if (p) memcpy(p + off, src, chunk);
        else for (u32 i = 0; i < chunk; i++) ps2_w8(addr + i, src[i]);
        addr += chunk;
        src += chunk;
        n -= chunk;
    }
}

static u32 hash_name(const char *s) {
    u32 h = 2166136261u;
    for (; *s; s++) { h ^= (u8)upc(*s); h *= 16777619u; }
    return h;
}

static void hash_insert(u32 index) {
    u32 i = hash_name(nodes[index]->f.name) & (nslots - 1u);
    while (slots[i]) i = (i + 1u) & (nslots - 1u);
    slots[i] = index + 1u;
}

static void hash_grow(void) {
    u32 want = 1024;
    while (want < nnodes * 2u + 2u) want *= 2u;
    if (want <= nslots) return;
    free(slots);
    slots = (u32 *)calloc(want, sizeof *slots);
    if (!slots) ps2_fatal("vfs: out of memory indexing the disc");
    nslots = want;
    for (u32 i = 0; i < nnodes; i++) hash_insert(i);
}

static vfs_node *lookup(const char *normalised) {
    u32 i;
    if (!nslots) return NULL;
    for (i = hash_name(normalised) & (nslots - 1u); slots[i];
         i = (i + 1u) & (nslots - 1u)) {
        vfs_node *n = nodes[slots[i] - 1u];
        if (ieq(n->f.name, normalised)) return n;
    }
    return NULL;
}

static vfs_node *add_node(const char *name, u32 size) {
    vfs_node *n;
    if (strlen(name) >= sizeof n->f.name) {
        ps2_log("vfs: path too long for the disc index, skipped: %s", name);
        return NULL;
    }
    if (nnodes == cnodes) {
        cnodes = cnodes ? cnodes * 2u : 256u;
        nodes = (vfs_node **)realloc(nodes, cnodes * sizeof *nodes);
        if (!nodes) ps2_fatal("vfs: out of memory building the disc index");
    }
    n = (vfs_node *)calloc(1, sizeof *n);
    if (!n) ps2_fatal("vfs: out of memory building the disc index");
    snprintf(n->f.name, sizeof n->f.name, "%s", name);
    n->f.size = size;
    n->disc_size = size;
    nodes[nnodes++] = n;
    if (nnodes * 2u >= nslots) hash_grow();
    else hash_insert(nnodes - 1u);
    return n;
}

static void node_read(vfs_node *n, u64 pos, u32 len, u8 *dst) {
    u32 data = 0;
    if (pos < n->f.size) {
        u64 left = (u64)n->f.size - pos;
        data = left < len ? (u32)left : len;
    }
    if (data < len) memset(dst + data, 0, len - data);
    if (!data) return;
    switch (n->src) {
    case SRC_IMAGE:
        if (image_fp && seek64(image_fp, n->image_off + pos) == 0
            && fread(dst, 1, data, image_fp) == data)
            return;
        break;
    case SRC_TREE:
    case SRC_HOST: {
        FILE *fp = handle_for(n->host);
        size_t got;
        if (!fp || seek64(fp, pos) != 0) break;
        got = fread(dst, 1, data, fp);
        if (n->src == SRC_HOST) reads_from_mods++;
        if (got == data) return;
        memset(dst + got, 0, data - got);
        if (!n->failed) {
            n->failed = 1;
            ps2_log("vfs: '%s' is shorter on disk than when it was indexed "
                    "(%s); the rest reads as zeros", n->f.name, n->host);
        }
        return;
    }
    }
    memset(dst, 0, data);
    if (!n->failed) {
        n->failed = 1;
        ps2_log("vfs: cannot read '%s' from %s; it reads as zeros", n->f.name,
                n->src == SRC_IMAGE ? "the disc image" : n->host);
    }
}

static vfs_node *node_at(u32 lsn) {
    u32 lo = 0, hi = nnodes;
    while (lo < hi) {
        u32 mid = lo + (hi - lo) / 2u;
        vfs_node *n = nodes[mid];
        if (lsn < n->f.lsn) hi = mid;
        else if (lsn >= n->f.lsn + sectors_of(n->f.size)) lo = mid + 1u;
        else return n;
    }
    return NULL;
}

int ps2_vfs_read_sectors(u32 lsn, u32 sectors, void *dst) {
    u8 *out = (u8 *)dst;
    u32 done = 0;
    if (!vfs_opened) return -1;
    pthread_mutex_lock(&vfs_lock);
    reads_sectors += sectors;
    while (done < sectors) {
        vfs_node *n = node_at(lsn + done);
        u32 in, run;
        if (!n) {
            memset(out + (size_t)done * SECTOR, 0, SECTOR);
            done++;
            continue;
        }
        in = lsn + done - n->f.lsn;
        run = sectors_of(n->f.size) - in;
        if (run > sectors - done) run = sectors - done;
        node_read(n, (u64)in * SECTOR, run * SECTOR, out + (size_t)done * SECTOR);
        done += run;
    }
    pthread_mutex_unlock(&vfs_lock);
    return (int)sectors;
}

int ps2_vfs_read_sectors_guest(u32 lsn, u32 sectors, u32 guest_addr) {
    enum { CHUNK = 256 };
    u8 *buf;
    u32 done = 0;
    if (!vfs_opened) return -1;
    buf = (u8 *)malloc((size_t)(sectors < CHUNK ? (sectors ? sectors : 1u) : CHUNK)
                       * SECTOR);
    if (!buf) return -1;
    while (done < sectors) {
        u32 run = sectors - done < CHUNK ? sectors - done : CHUNK;
        ps2_vfs_read_sectors(lsn + done, run, buf);
        guest_put(guest_addr + done * SECTOR, buf, run * SECTOR);
        done += run;
    }
    free(buf);
    return (int)sectors;
}

int ps2_vfs_read(const ps2_disc_file *f, u64 pos, u32 len, void *dst) {
    vfs_node *n = (vfs_node *)(void *)f;
    if (!f || !vfs_opened) return -1;
    if (pos >= f->size) return 0;
    if (pos + len > f->size) len = (u32)((u64)f->size - pos);
    pthread_mutex_lock(&vfs_lock);
    node_read(n, pos, len, (u8 *)dst);
    reads_bytes += len;
    pthread_mutex_unlock(&vfs_lock);
    return (int)len;
}

int ps2_vfs_read_guest(const ps2_disc_file *f, u64 pos, u32 len,
                       u32 guest_addr) {
    enum { CHUNK = 1u << 20 };
    u8 *buf;
    u32 done = 0;
    if (!f || !vfs_opened) return -1;
    if (pos >= f->size) return 0;
    if (pos + len > f->size) len = (u32)((u64)f->size - pos);
    buf = (u8 *)malloc(len < CHUNK ? (len ? len : 1u) : CHUNK);
    if (!buf) return -1;
    while (done < len) {
        u32 run = len - done < CHUNK ? len - done : CHUNK;
        ps2_vfs_read(f, pos + done, run, buf);
        guest_put(guest_addr + done, buf, run);
        done += run;
    }
    free(buf);
    return (int)len;
}

const ps2_disc_file *ps2_vfs_find(const char *name) {
    char norm[256];
    vfs_node *n;
    if (!name || norm_path(name, norm, sizeof norm) <= 0) return NULL;
    n = lookup(norm);
    return n ? &n->f : NULL;
}

u32 ps2_vfs_file_count(void) { return nnodes; }
int ps2_vfs_ready(void) { return vfs_opened; }

static int image_sector(u32 lsn, u8 *dst) {
    return (image_fp && seek64(image_fp, (u64)lsn * SECTOR) == 0
            && fread(dst, 1, SECTOR, image_fp) == SECTOR) ? 0 : -1;
}

static void image_scan_dir(u32 lsn, u32 size, const char *prefix, int depth) {
    u8 buf[SECTOR];
    u32 sectors = (size + SECTOR - 1u) / SECTOR;
    for (u32 s = 0; s < sectors; s++) {
        u32 off = 0;
        if (image_sector(lsn + s, buf) != 0) break;
        while (off < SECTOR) {
            u8 len = buf[off];
            u32 elsn, esize, nlen;
            char name[128], full[256];
            if (len == 0 || off + len > SECTOR) break;
            memcpy(&elsn, buf + off + 2, 4);
            memcpy(&esize, buf + off + 10, 4);
            nlen = buf[off + 32];
            if (nlen == 1 && (buf[off + 33] == 0 || buf[off + 33] == 1)) {
                off += len;
                continue;
            }
            if (nlen > sizeof name - 1) nlen = sizeof name - 1;
            memcpy(name, buf + off + 33, nlen);
            name[nlen] = 0;
            for (u32 i = 0; i < nlen; i++)
                if (name[i] == ';') { name[i] = 0; break; }
            snprintf(full, sizeof full, "%s%s%s", prefix, *prefix ? "/" : "",
                     name);
            if (buf[off + 25] & 2) {
                if (depth < 8) image_scan_dir(elsn, esize, full, depth + 1);
            } else {
                vfs_node *n = add_node(full, esize);
                if (n) {
                    n->src = SRC_IMAGE;
                    n->image_off = (u64)elsn * SECTOR;
                    memcpy(n->f.date, buf + off + 18, 7);
                }
            }
            off += len;
        }
    }
}

static void tree_scan(const char *hostdir, const char *prefix, int depth) {
    DIR *d = opendir(hostdir);
    struct dirent *e;
    if (!d) return;
    while ((e = readdir(d)) != NULL) {
        char hp[1024], full[256];
        u64 size;
        int is_dir, hn, fn;
        if (e->d_name[0] == '.') continue;
        hn = snprintf(hp, sizeof hp, "%s/%s", hostdir, e->d_name);
        fn = snprintf(full, sizeof full, "%s%s%s", prefix, *prefix ? "/" : "",
                      e->d_name);
        if (hn < 0 || (size_t)hn >= sizeof hp || fn < 0
            || (size_t)fn >= sizeof full) {
            ps2_log("vfs: path too long, not indexed: %s/%s", hostdir, e->d_name);
            continue;
        }
        if (host_stat(hp, &size, &is_dir) != 0) continue;
        if (is_dir) {
            if (depth < 8) tree_scan(hp, full, depth + 1);
        } else if (size > 0xFFFFFFFFull) {
            ps2_log("vfs: '%s' is larger than a disc file can be; not indexed",
                    hp);
        } else {
            vfs_node *n = add_node(full, (u32)size);
            if (n) {
                n->src = SRC_TREE;
                n->host = xstrdup(hp);
            }
        }
    }
    closedir(d);
}

static int claim_beats(const vfs_claim *a, const vfs_claim *b) {
    if (a->priority != b->priority) return a->priority > b->priority ? 1 : -1;
    return a->order > b->order ? 1 : -1;
}

static void say_conflict(const char *what, const vfs_claim *win,
                         const vfs_claim *lose) {
    nconflicts++;
    ps2_log("vfs: conflict on %s -- %s (priority %d, '%s') wins over %s "
            "(priority %d, '%s')", what, win->owner, win->priority, win->path,
            lose->owner, lose->priority, lose->path);
}

s64 ps2_vfs_stat(const char *path) {
    char norm[512];
    vfs_node *n;
    s64 size = -1;
    if (!path || norm_path(path, norm, sizeof norm) <= 0 || !vfs_opened) return -1;
    pthread_mutex_lock(&vfs_lock);
    n = lookup(norm);
    if (n) size = n->f.size;
    pthread_mutex_unlock(&vfs_lock);
    return size;
}

s64 ps2_vfs_read_path(const char *path, u64 pos, u32 len, void *dst) {
    char norm[512];
    vfs_node *n;
    s64 got = -1;
    if (!path || norm_path(path, norm, sizeof norm) <= 0 || !vfs_opened) return -1;
    pthread_mutex_lock(&vfs_lock);
    n = lookup(norm);
    if (n) {
        if (pos >= n->f.size) got = 0;
        else {
            u64 left = (u64)n->f.size - pos;
            got = left < len ? (s64)left : (s64)len;
            node_read(n, pos, (u32)got, (u8 *)dst);
        }
    }
    pthread_mutex_unlock(&vfs_lock);
    return got;
}

void ps2_vfs_claim(const char *path, const char *host, u64 size, int priority,
                   const char *owner) {
    char norm[512];
    vfs_claim *c;
    if (vfs_opened) {
        ps2_log("vfs: %s's '%s' arrived after the disc was opened; ignored",
                owner ? owner : "?", path);
        return;
    }
    if (norm_path(path, norm, sizeof norm) <= 0) {
        ps2_log("vfs: %s's '%s' is not a usable path; ignored",
                owner ? owner : "?", path);
        return;
    }
    if (nclaims == cclaims) {
        cclaims = cclaims ? cclaims * 2u : 64u;
        claims = (vfs_claim **)realloc(claims, cclaims * sizeof *claims);
        if (!claims) ps2_fatal("vfs: out of memory recording a mod file");
    }
    c = (vfs_claim *)calloc(1, sizeof *c);
    if (!c) ps2_fatal("vfs: out of memory recording a mod file");
    c->path = xstrdup(norm);
    c->host = xstrdup(host);
    c->size = size;
    c->priority = priority;
    c->order = nclaims;
    c->owner = owner ? owner : "?";
    claims[nclaims++] = c;
}

static int claim_ptr_cmp(const void *a, const void *b) {
    const vfs_claim *x = *(const vfs_claim *const *)a;
    const vfs_claim *y = *(const vfs_claim *const *)b;
    int c = icmp(x->path, y->path);
    if (c) return c;
    return claim_beats(x, y) > 0 ? 1 : -1;
}

static void settle_file(vfs_claim **run, u32 i, u32 j, vfs_node *n) {
    vfs_claim *win = run[j - 1];
    claim_kind kind = n ? CL_DISC : CL_NEW;
    for (u32 x = i; x < j; x++) run[x]->kind = kind;
    for (u32 x = i; x + 1u < j; x++) {
        char what[300];
        snprintf(what, sizeof what, "'%s'", win->path);
        say_conflict(what, win, run[x]);
    }
    if (win->size > 0xFFFFFFFFull) {
        win->kind = CL_BAD;
        ps2_log("vfs: %s's '%s' is %llu bytes; a disc file cannot be over 4 GB",
                win->owner, win->path, (unsigned long long)win->size);
        return;
    }
    if (n) {
        ps2_log("vfs: %s replaces '%s' (%llu bytes, was %u)", win->owner,
                n->f.name, (unsigned long long)win->size, n->disc_size);
    } else {
        n = add_node(win->path, 0);
        if (!n) { win->kind = CL_BAD; return; }
        ps2_log("vfs: %s adds '%s', which is not a file the game has -- a new "
                "file that code mods can read.  If it was meant to replace one "
                "of the game's files, the name is wrong.", win->owner, win->path);
    }
    n->src = SRC_HOST;
    n->host = win->host;
    n->f.size = (u32)win->size;
    n->claim = win;
    win->won = 1;
}

static void resolve_claims(void) {
    vfs_claim **run = (vfs_claim **)malloc((nclaims ? nclaims : 1u) * sizeof *run);
    if (!run) ps2_fatal("vfs: out of memory resolving mods");
    memcpy(run, claims, nclaims * sizeof *run);
    if (nclaims > 1) qsort(run, nclaims, sizeof *run, claim_ptr_cmp);
    for (u32 i = 0; i < nclaims;) {
        u32 j = i;
        while (j < nclaims && !icmp(run[j]->path, run[i]->path)) j++;
        settle_file(run, i, j, lookup(run[i]->path));
        i = j;
    }
    free(run);
}

int ps2_vfs_open(const char *path) {
    u64 size;
    int is_dir;
    if (vfs_opened) return 0;
    if (!path || !*path || host_stat(path, &size, &is_dir) != 0) {
        ps2_log("vfs: no disc at '%s'", path ? path : "");
        return -1;
    }
    snprintf(vfs_path, sizeof vfs_path, "%s", path);
    if (is_dir) {
        vfs_is_tree = 1;
        tree_scan(path, "", 0);
    } else {
        u8 pvd[SECTOR];
        u32 root_lsn, root_size;
        image_fp = fopen(path, "rb");
        if (!image_fp || image_sector(16, pvd) != 0
            || memcmp(pvd + 1, "CD001", 5) != 0) {
            ps2_log("vfs: '%s' is not an ISO9660 image", path);
            if (image_fp) fclose(image_fp);
            image_fp = NULL;
            return -1;
        }
        memcpy(&root_lsn, pvd + 156 + 2, 4);
        memcpy(&root_size, pvd + 156 + 10, 4);
        image_scan_dir(root_lsn, root_size, "", 0);
    }
    if (!nnodes) {
        ps2_log("vfs: '%s' has no files", path);
        return -1;
    }
    resolve_claims();

    {
        u32 lsn = FIRST_LSN;
        for (u32 i = 0; i < nnodes; i++) {
            nodes[i]->f.lsn = lsn;
            lsn += sectors_of(nodes[i]->f.size);
        }
        end_lsn = lsn;
    }
    vfs_opened = 1;
    ps2_log("vfs: %s '%s', %u files, sectors %u..%u", vfs_is_tree
            ? "extracted tree" : "disc image", path, nnodes, FIRST_LSN, end_lsn);
    return 0;
}

void ps2_vfs_owner_stats(const char *owner, u32 *files) {
    u32 n = 0;
    for (u32 i = 0; i < nclaims; i++) {
        if (!owner || strcmp(claims[i]->owner, owner)) continue;
        n += claims[i]->won;
    }
    if (files) *files = n;
}

void ps2_vfs_report(void) {
    u32 replaced = 0, added = 0, bad = 0;
    if (!vfs_opened) return;
    for (u32 i = 0; i < nclaims; i++) {
        const vfs_claim *c = claims[i];
        if (c->kind == CL_DISC && c->won) replaced++;
        else if (c->kind == CL_NEW && c->won) added++;
        else if (c->kind == CL_BAD) bad++;
    }
    ps2_log("---- filesystem ----");
    ps2_log("   %s '%s': %u files, sectors %u..%u", vfs_is_tree
            ? "extracted tree" : "disc image", vfs_path, nnodes, FIRST_LSN,
            end_lsn);
    ps2_log("   %llu sector(s) and %llu byte(s) read, %llu read(s) from mod files",
            (unsigned long long)reads_sectors, (unsigned long long)reads_bytes,
            (unsigned long long)reads_from_mods);
    if (!nclaims) return;
    for (u32 i = 0; i < nnodes; i++)
        if (nodes[i]->claim)
            ps2_log("   %-8s %-32s %10u bytes  from %s",
                    nodes[i]->claim->kind == CL_NEW ? "new" : "replaced",
                    nodes[i]->f.name, nodes[i]->f.size, nodes[i]->claim->owner);
    if (replaced || added)
        ps2_log("   %u whole file(s) replaced, %u new file(s)", replaced, added);
    if (nconflicts)
        ps2_log("   %u conflict(s) between mods, each named above", nconflicts);
    if (bad)
        ps2_log("   %u mod file(s) could not be placed, each named above", bad);
}
