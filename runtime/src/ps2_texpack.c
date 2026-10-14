/* Replacement ("HD") texture packs -- see ps2_texpack.h.

   The pack directory (textures/hd, or PS2_TEXTURE_PACK; "off" disables it) is
   indexed at start-up, subfolders included.  A replacement is read from disk
   on a loader thread the first time its texture is drawn, so entering a scene
   does not stall the game; until it arrives the original is drawn.  Loaded
   pixels are kept for the session (the renderer uploads straight from them),
   up to PS2_TEXTURE_PACK_MB (default 4096); past that the originals are used.

   Dumping (the menu switch, or PS2_TEXTURE_DUMP=<dir>) saves each texture the
   second time it is seen in a different field, so movie frames and other
   pictures that change every frame are not saved.  dump_info.tsv records how
   each was sampled (wrap modes, atlas window) for tools/texture_pack.py. */
#include "ps2_texpack.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <pthread.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#define mkdir_one(p) _mkdir(p)
#else
#define mkdir_one(p) mkdir((p), 0755)
#endif

extern void ps2_log(const char *, ...);

enum { ST_NONE = 0, ST_QUEUED, ST_READY, ST_FAILED };

typedef struct {
    uint64_t id;
    unsigned w, h, rw, rh;
    int state;                  /* ST_*, written by the loader with release */
    char *path;
    unsigned char *data;
} pack_entry;

static pack_entry *entries;
static unsigned count, cap_entries;
static int32_t *slots;           /* open addressing: entry index + 1, 0 = empty */
static unsigned nslots;
static int initialized, enabled = 1, dumping;
static char pack_dir[1024], dump_dir[1024];
static uint64_t loaded_bytes, budget_bytes = 4096ull << 20;
static unsigned loads_logged, rejects;

/* dump bookkeeping: id -> first field seen + 1 (or ~0 once saved) */
typedef struct { uint64_t id; uint32_t frame; } seen_t;
static seen_t *seen;
static unsigned nseen, seen_cap;
static uint64_t dump_bytes, dump_budget = 4096ull << 20;
static unsigned ndumped;

static pthread_mutex_t q_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t q_cv = PTHREAD_COND_INITIALIZER;
static unsigned queue[4096], q_head, q_tail;
static int loader_started;

uint64_t ps2_texpack_id(const unsigned char *rgba, unsigned w, unsigned h) {
    uint64_t id = UINT64_C(14695981039346656037);
    for (unsigned k = 0; k < 8; k++) {
        unsigned v = k < 4 ? w : h;
        id = (id ^ ((v >> ((k & 3u) * 8u)) & 255u)) * UINT64_C(1099511628211);
    }
    for (size_t k = 0; k < (size_t)w * h * 4; k++)
        id = (id ^ rgba[k]) * UINT64_C(1099511628211);
    return id;
}

static unsigned slot_of(uint64_t id) { return (unsigned)((id ^ (id >> 29)) * 0x9E3779B1u); }

static void map_add(unsigned i) {
    unsigned m = nslots - 1u, s = slot_of(entries[i].id) & m;
    while (slots[s]) s = (s + 1u) & m;
    slots[s] = (int32_t)i + 1;
}

static pack_entry *find(uint64_t id, unsigned w, unsigned h) {
    unsigned m, s;
    if (!nslots) return NULL;
    m = nslots - 1u;
    for (s = slot_of(id) & m; slots[s]; s = (s + 1u) & m) {
        pack_entry *e = &entries[slots[s] - 1];
        if (e->id == id && e->w == w && e->h == h) return e;
    }
    return NULL;
}

/* Files directly in a folder are indexed before its subfolders, so a
   replacement made by hand in textures/hd wins over one generated into
   textures/hd/upscaled. */
static void index_file(const char *path, const char *name) {
    unsigned long long id;
    unsigned w, h;
    int n = 0;
    if (sscanf(name, "%16llx_%ux%u.pam%n", &id, &w, &h, &n) != 3 || !n || name[n]
        || !w || !h || w > 4096 || h > 4096 || find(id, w, h))
        return;
    if (count == cap_entries) {
        unsigned nc = cap_entries ? cap_entries * 2u : 1024u;
        pack_entry *ne = realloc(entries, nc * sizeof *ne);
        if (!ne) return;
        entries = ne; cap_entries = nc;
    }
    if ((count + 1u) * 2u > nslots) {             /* grow and rehash */
        unsigned ns = nslots ? nslots * 2u : 4096u;
        int32_t *nsl = calloc(ns, sizeof *nsl);
        if (!nsl) return;
        free(slots); slots = nsl; nslots = ns;
        for (unsigned i = 0; i < count; i++) map_add(i);
    }
    memset(&entries[count], 0, sizeof entries[count]);
    entries[count].id = id;
    entries[count].w = w;
    entries[count].h = h;
    if (!(entries[count].path = strdup(path))) return;
    map_add(count++);
}

/* Files directly in a folder are indexed before its subfolders, so a
   replacement made by hand in textures/hd wins over one generated into
   textures/hd/upscaled. */
static void index_dir(const char *dir, int depth) {
    for (int pass = 0; pass < 2; pass++) {
        DIR *d = opendir(dir);
        struct dirent *e;
        if (!d) return;
        while ((e = readdir(d))) {
            char path[1400];
            struct stat st;
            if (e->d_name[0] == '.') continue;
            if (snprintf(path, sizeof path, "%s/%s", dir, e->d_name) >= (int)sizeof path) continue;
            if (pass == 0) index_file(path, e->d_name);
            else if (depth < 4 && !stat(path, &st) && S_ISDIR(st.st_mode))
                index_dir(path, depth + 1);
        }
        closedir(d);
    }
}

static void init(void) {
    const char *p = getenv("PS2_TEXTURE_PACK"), *d = getenv("PS2_TEXTURE_DUMP");
    const char *mb = getenv("PS2_TEXTURE_PACK_MB");
    initialized = 1;
    if (mb && *mb) {
        unsigned long long v = strtoull(mb, NULL, 0);
        if (v) budget_bytes = (uint64_t)v << 20;
    }
    if (d && *d && strlen(d) < sizeof dump_dir) {
        snprintf(dump_dir, sizeof dump_dir, "%s", d);
        dumping = 1;
    }
    if (p && (!strcmp(p, "off") || !strcmp(p, "0"))) {
        ps2_log("texture-pack: off (PS2_TEXTURE_PACK=%s)", p);
        return;
    }
    if (!p || !*p) p = "textures/hd";
    if (strlen(p) >= sizeof pack_dir) return;
    snprintf(pack_dir, sizeof pack_dir, "%s", p);
    index_dir(pack_dir, 0);
    if (count)
        ps2_log("texture-pack: %u replacement textures in %s (up to %llu MB loaded)",
                count, pack_dir, (unsigned long long)(budget_bytes >> 20));
}

static void ensure_init(void) { if (!initialized) init(); }

int ps2_texpack_active(void) {
    ensure_init();
    return (enabled && count) || dumping;
}
unsigned ps2_texpack_count(void) { ensure_init(); return count; }
const char *ps2_texpack_dir(void) { ensure_init(); return pack_dir; }
void ps2_texpack_memory(uint64_t *used, uint64_t *limit) {
    *used = __atomic_load_n(&loaded_bytes, __ATOMIC_RELAXED);
    *limit = budget_bytes;
}
void ps2_texpack_set_enabled(int on) { ensure_init(); enabled = on != 0; }
int ps2_texpack_enabled(void) { ensure_init(); return enabled; }
int ps2_texpack_dumping(void) { ensure_init(); return dumping; }
unsigned ps2_texpack_dumped(void) { return ndumped; }

static void mkdirs(const char *path) {
    char tmp[1024];
    size_t n = strlen(path);
    if (n >= sizeof tmp) return;
    memcpy(tmp, path, n + 1);
    for (size_t i = 1; i <= n; i++)
        if (tmp[i] == '/' || tmp[i] == '\\' || !tmp[i]) {
            char c = tmp[i];
            tmp[i] = 0;
            mkdir_one(tmp);
            tmp[i] = c;
        }
}

void ps2_texpack_set_dump(int on) {
    ensure_init();
    if (on && !*dump_dir) snprintf(dump_dir, sizeof dump_dir, "textures/dump");
    if (on && !dumping) {
        mkdirs(dump_dir);
        ps2_log("texture-pack: saving textures for upscaling into %s", dump_dir);
    }
    dumping = on != 0;
}

/* ---- loading ---- */

static int load_entry(pack_entry *e) {
    char line[128];
    unsigned x = 0, y = 0, depth = 0, maxval = 0, lines = 0;
    int end = 0, type = 0;
    size_t bytes;
    unsigned char *data;
    FILE *f = fopen(e->path, "rb");
    if (!f) return 0;
    if (!fgets(line, sizeof line, f) || (strcmp(line, "P7\n") && strcmp(line, "P7\r\n"))) goto bad;
    while (lines++ < 16 && fgets(line, sizeof line, f)) {
        if (!strcmp(line, "ENDHDR\n") || !strcmp(line, "ENDHDR\r\n")) { end = 1; break; }
        if (sscanf(line, "WIDTH %u", &x) == 1) continue;
        if (sscanf(line, "HEIGHT %u", &y) == 1) continue;
        if (sscanf(line, "DEPTH %u", &depth) == 1) continue;
        if (sscanf(line, "MAXVAL %u", &maxval) == 1) continue;
        if (!strcmp(line, "TUPLTYPE RGB_ALPHA\n") || !strcmp(line, "TUPLTYPE RGB_ALPHA\r\n")) type = 1;
    }
    if (!end || !type || depth != 4 || maxval != 255 || x < e->w || y < e->h
        || x > 4096 || y > 4096 || x % e->w || y % e->h || x / e->w != y / e->h
        || x / e->w > 8) goto bad;
    bytes = (size_t)x * y * 4;
    if (__atomic_add_fetch(&loaded_bytes, bytes, __ATOMIC_RELAXED) > budget_bytes) {
        static int said;
        __atomic_sub_fetch(&loaded_bytes, bytes, __ATOMIC_RELAXED);
        if (!said) {
            said = 1;
            ps2_log("texture-pack: %llu MB of replacements loaded, the limit -- further "
                    "textures keep their originals (PS2_TEXTURE_PACK_MB raises it)",
                    (unsigned long long)(budget_bytes >> 20));
        }
        fclose(f);
        return 0;
    }
    data = malloc(bytes);
    if (!data || fread(data, 1, bytes, f) != bytes || fgetc(f) != EOF) {
        free(data);
        __atomic_sub_fetch(&loaded_bytes, bytes, __ATOMIC_RELAXED);
        goto bad;
    }
    fclose(f);
    e->data = data;
    e->rw = x;
    e->rh = y;
    if (loads_logged < 16u) {
        loads_logged++;
        ps2_log("texture-pack: loaded %016llx %ux%u -> %ux%u%s", (unsigned long long)e->id,
                e->w, e->h, x, y, loads_logged == 16u ? " (no more of these)" : "");
    }
    return 1;
bad:
    fclose(f);
    if (rejects++ < 16u) ps2_log("texture-pack: rejected %s; using the original", e->path);
    return 0;
}

static void *loader_main(void *arg) {
    (void)arg;
    for (;;) {
        unsigned i;
        pthread_mutex_lock(&q_lock);
        while (q_head == q_tail) pthread_cond_wait(&q_cv, &q_lock);
        i = queue[q_tail++ & 4095u];
        pthread_mutex_unlock(&q_lock);
        __atomic_store_n(&entries[i].state, load_entry(&entries[i]) ? ST_READY : ST_FAILED,
                         __ATOMIC_RELEASE);
    }
    return NULL;
}

static int enqueue(unsigned i) {
    int ok = 0;
    pthread_mutex_lock(&q_lock);
    if (!loader_started) {
        pthread_t t;
        loader_started = pthread_create(&t, NULL, loader_main, NULL) == 0 ? 1 : -1;
        if (loader_started > 0) pthread_detach(t);
    }
    if (loader_started > 0 && q_head - q_tail < 4096u) {
        queue[q_head++ & 4095u] = i;
        ok = 1;
        pthread_cond_signal(&q_cv);
    }
    pthread_mutex_unlock(&q_lock);
    return ok;
}

const unsigned char *ps2_texpack_get(uint64_t id, unsigned w, unsigned h,
                                     unsigned *rw, unsigned *rh, int *pending) {
    pack_entry *e;
    int st;
    *pending = 0;
    ensure_init();
    if (!enabled || !count || !(e = find(id, w, h))) return NULL;
    st = __atomic_load_n(&e->state, __ATOMIC_ACQUIRE);
    if (st == ST_READY) { *rw = e->rw; *rh = e->rh; return e->data; }
    if (st == ST_FAILED) return NULL;
    if (st == ST_NONE) {
        __atomic_store_n(&e->state, ST_QUEUED, __ATOMIC_RELAXED);
        if (!enqueue((unsigned)(e - entries))) {
            __atomic_store_n(&e->state, ST_NONE, __ATOMIC_RELAXED);
            /* no thread: load here */
            if (loader_started < 0) {
                __atomic_store_n(&e->state, load_entry(e) ? ST_READY : ST_FAILED,
                                 __ATOMIC_RELEASE);
                return ps2_texpack_get(id, w, h, rw, rh, pending);
            }
        }
    }
    *pending = 1;
    return NULL;
}

/* ---- dumping ---- */

static int seen_note(uint64_t id, unsigned frame, int now) {
    /* returns 1 when this picture should be saved now */
    unsigned m, s;
    if ((nseen + 1u) * 2u > seen_cap) {
        unsigned nc = seen_cap ? seen_cap * 2u : 8192u, i, oc = seen_cap;
        seen_t *old = seen, *ns = calloc(nc, sizeof *ns);
        if (!ns) return 0;
        seen = ns;
        seen_cap = nc;
        m = seen_cap - 1u;
        for (i = 0; i < oc; i++) {
            if (!old[i].frame) continue;
            for (s = slot_of(old[i].id) & m; seen[s].frame; s = (s + 1u) & m) {}
            seen[s] = old[i];
        }
        free(old);
    }
    m = seen_cap - 1u;
    for (s = slot_of(id) & m; seen[s].frame; s = (s + 1u) & m)
        if (seen[s].id == id) {
            if (seen[s].frame == 0xFFFFFFFFu) return 0;
            /* still the same picture at least 4 fields later */
            if (now || frame + 1u - seen[s].frame >= 4u) { seen[s].frame = 0xFFFFFFFFu; return 1; }
            return 0;
        }
    seen[s].id = id;
    seen[s].frame = now ? 0xFFFFFFFFu : frame + 1u;
    nseen++;
    return now;
}

void ps2_texpack_dump(const unsigned char *rgba, unsigned w, unsigned h, uint64_t id,
                      const ps2_texpack_use *use) {
    char path[1200];
    FILE *f;
    size_t bytes = (size_t)w * h * 4;
    if (!dumping || !*dump_dir || w < 8u || h < 8u || w > 4096u || h > 4096u) return;
    if (bytes > dump_budget - dump_bytes) return;
    if (snprintf(path, sizeof path, "%s/%016llx_%ux%u.pam", dump_dir,
                 (unsigned long long)id, w, h) >= (int)sizeof path) return;
    f = fopen(path, "rb");                /* never overwrite an earlier dump */
    if (f) { fclose(f); return; }
    f = fopen(path, "wb");
    if (!f) return;
    fprintf(f, "P7\nWIDTH %u\nHEIGHT %u\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n", w, h);
    {
        int ok = fwrite(rgba, 1, bytes, f) == bytes;
        if (fclose(f)) ok = 0;
        if (!ok) { remove(path); return; }
    }
    dump_bytes += bytes;
    ndumped++;
    if (snprintf(path, sizeof path, "%s/dump_info.tsv", dump_dir) < (int)sizeof path
        && (f = fopen(path, "a"))) {
        fprintf(f, "%016llx_%ux%u\t%u\t%u\t%u\n", (unsigned long long)id, w, h,
                use ? use->wms : 0u, use ? use->wmt : 0u, use ? use->region : 0u);
        fclose(f);
    }
}

int ps2_texpack_want_dump(uint64_t id, unsigned frame) {
    ensure_init();
    return dumping && *dump_dir && seen_note(id, frame, 0);
}

const unsigned char *ps2_texpack_lookup(const unsigned char *rgba, unsigned w,
    unsigned h, unsigned *rw, unsigned *rh, uint64_t *id) {
    const unsigned char *p;
    pack_entry *e;
    int pending;
    ensure_init();
    if (!rgba || w < 8 || h < 8 || w > 4096 || h > 4096) return NULL;
    *id = ps2_texpack_id(rgba, w, h);
    if (dumping && seen_note(*id, 0, 1)) ps2_texpack_dump(rgba, w, h, *id, NULL);
    if (!enabled || !(e = find(*id, w, h))) return NULL;
    if (__atomic_load_n(&e->state, __ATOMIC_ACQUIRE) == ST_NONE)
        __atomic_store_n(&e->state, load_entry(e) ? ST_READY : ST_FAILED, __ATOMIC_RELEASE);
    while (!(p = ps2_texpack_get(*id, w, h, rw, rh, &pending)) && pending) {}
    return p;
}
