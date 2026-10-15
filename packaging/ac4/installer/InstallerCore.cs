using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;

// No game files are embedded. The supported ELF is checked and its load image
// is reconstructed from the user's ISO using the recompiler's PT_LOAD layout.
internal static class InstallerCore
{
    internal const string ElfHash = "38ECEBD6965C2F74EC8973F538781506BF3A2CFAD86F908DEB6C5D585D528301";
    internal const int ElfSize = 3248756;
    internal const uint ImageBase = 0x100000;
    internal const int ImageSize = 0x3cc74c;
    const int Sector = 2048;
    struct Entry { internal long Offset; internal int Length; }

    static uint U32(byte[] b, int p) { return BitConverter.ToUInt32(b, p); }
    static byte[] Read(Stream s, long offset, int length)
    {
        if (offset < 0 || length < 0 || offset > s.Length - length)
            throw new InvalidDataException("The ISO is truncated or has an invalid file extent.");
        byte[] b = new byte[length]; s.Position = offset;
        for (int n = 0; n < length; ) {
            int got = s.Read(b, n, length - n);
            if (got == 0) throw new EndOfStreamException("The ISO could not be read completely.");
            n += got;
        }
        return b;
    }

    static Entry Find(Stream iso, byte[] directory, string name)
    {
        for (int p = 0; p < directory.Length; ) {
            int n = directory[p];
            if (n == 0) { p = (p / Sector + 1) * Sector; continue; }
            if (n < 34 || p + n > directory.Length || p % Sector + n > Sector)
                throw new InvalidDataException("The ISO directory is damaged.");
            int chars = directory[p + 32];
            if (33 + chars > n) throw new InvalidDataException("Invalid ISO file name.");
            string found = Encoding.ASCII.GetString(directory, p + 33, chars).Split(';')[0];
            if (String.Equals(found, name, StringComparison.OrdinalIgnoreCase)) {
                if ((directory[p + 25] & (2 | 128)) != 0)
                    throw new InvalidDataException("Unsupported ISO file layout for " + name);
                long offset = ((long)U32(directory, p + 2) + directory[p + 1]) * Sector;
                uint length = U32(directory, p + 10);
                if (length > Int32.MaxValue || offset > iso.Length - length)
                    throw new InvalidDataException("Invalid ISO file extent.");
                return new Entry { Offset = offset, Length = (int)length };
            }
            p += n;
        }
        throw new InvalidDataException("This is not the supported Ace Combat 04 USA ISO: missing " + name + ".");
    }

    internal static byte[] ValidateIso(Stream iso)
    {
        if (iso.Length < 17 * Sector || iso.Length % Sector != 0)
            throw new InvalidDataException("Select an uncompressed ISO with 2048-byte sectors.");
        byte[] pvd = Read(iso, 16 * Sector, Sector);
        if (pvd[0] != 1 || Encoding.ASCII.GetString(pvd, 1, 5) != "CD001" || pvd[6] != 1
            || BitConverter.ToUInt16(pvd, 128) != Sector || (long)U32(pvd, 80) * Sector > iso.Length)
            throw new InvalidDataException("The file is not a complete ISO9660 game disc.");
        uint rootSize = U32(pvd, 166);
        if (rootSize < 34 || rootSize > 4 * 1024 * 1024)
            throw new InvalidDataException("Invalid ISO root directory.");
        byte[] root = Read(iso, ((long)U32(pvd, 158) + pvd[157]) * Sector, (int)rootSize);
        Entry cnf = Find(iso, root, "SYSTEM.CNF");
        if (cnf.Length > 65536) throw new InvalidDataException("Invalid SYSTEM.CNF.");
        string boot = Encoding.ASCII.GetString(Read(iso, cnf.Offset, cnf.Length));
        if (boot.IndexOf("SLUS_201.52", StringComparison.OrdinalIgnoreCase) < 0)
            throw new InvalidDataException("This region or revision is unsupported. Use the USA disc (SLUS-20152).");
        Entry entry = Find(iso, root, "SLUS_201.52");
        if (entry.Length != ElfSize)
            throw new InvalidDataException("The game executable has an unsupported size. Use an unmodified USA ISO.");
        byte[] elf = Read(iso, entry.Offset, entry.Length);
        using (SHA256 hash = SHA256.Create()) {
            string actual = BitConverter.ToString(hash.ComputeHash(elf)).Replace("-", "");
            if (actual != ElfHash)
                throw new InvalidDataException("The game executable does not match SLUS-20152. Modified or different-revision ISOs are not supported.");
        }
        return BuildImage(elf);
    }

    internal static byte[] BuildImage(byte[] elf)
    {
        if (elf.Length < 52 || elf[0] != 127 || Encoding.ASCII.GetString(elf, 1, 3) != "ELF"
            || elf[4] != 1 || elf[5] != 1 || BitConverter.ToUInt16(elf, 18) != 8)
            throw new InvalidDataException("Invalid game ELF.");
        uint phoff = U32(elf, 28);
        int stride = BitConverter.ToUInt16(elf, 42), count = BitConverter.ToUInt16(elf, 44);
        if (stride < 32 || count == 0 || (long)phoff + (long)stride * count > elf.Length)
            throw new InvalidDataException("Invalid ELF program headers.");
        byte[] image = new byte[ImageSize];
        uint lowest = UInt32.MaxValue; long highest = 0;
        for (int i = 0; i < count; i++) {
            int p = checked((int)phoff + stride * i);
            if (U32(elf, p) != 1 || U32(elf, p + 20) == 0) continue;
            uint offset = U32(elf, p + 4), address = U32(elf, p + 8);
            uint size = U32(elf, p + 16), memory = U32(elf, p + 20);
            if (size > memory || address < ImageBase || (long)address + memory > ImageBase + ImageSize
                || (long)offset + size > elf.Length)
                throw new InvalidDataException("The ELF load layout is unsupported.");
            Buffer.BlockCopy(elf, (int)offset, image, (int)(address - ImageBase), (int)size);
            lowest = Math.Min(lowest, address); highest = Math.Max(highest, (long)address + memory);
        }
        if (lowest != ImageBase || highest != ImageBase + ImageSize)
            throw new InvalidDataException("The game's memory layout does not match this runtime.");
        return image;
    }

    internal static string SafeTarget(string root, string relative)
    {
        string prefix = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        string full = Path.GetFullPath(Path.Combine(prefix, relative));
        if (!full.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("The installer contains an invalid payload path.");
        return full;
    }

    internal static void Extract(Stream payload, string stage, CancellationToken cancel)
    {
        using (ZipArchive zip = new ZipArchive(payload, ZipArchiveMode.Read, true)) {
            foreach (ZipArchiveEntry entry in zip.Entries) {
                cancel.ThrowIfCancellationRequested();
                string path = SafeTarget(stage, entry.FullName.Replace('/', Path.DirectorySeparatorChar));
                if (entry.FullName.EndsWith("/")) { Directory.CreateDirectory(path); continue; }
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                using (Stream input = entry.Open())
                using (FileStream output = new FileStream(path, FileMode.CreateNew)) input.CopyTo(output);
            }
        }
    }

    internal static void CreateShortcut(string path, string destination)
    {
        object shell = null, shortcut = null;
        try {
            shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell", true));
            shortcut = shell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { path });
            Type t = shortcut.GetType();
            t.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { Path.Combine(destination, "Ace Combat 04.exe") });
            t.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, shortcut, new object[] { destination });
            t.InvokeMember("IconLocation", BindingFlags.SetProperty, null, shortcut, new object[] { Path.Combine(destination, "Ace Combat 04.exe") + ",0" });
            t.InvokeMember("Description", BindingFlags.SetProperty, null, shortcut, new object[] { "Ace Combat 04: Shattered Skies - PC Port" });
            t.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
        }
        finally {
            if (shortcut != null) Marshal.FinalReleaseComObject(shortcut);
            if (shell != null) Marshal.FinalReleaseComObject(shell);
        }
    }

    internal static void Install(string isoPath, string destination, string shortcutPath,
                                 Stream payload, Action<int, string> progress, CancellationToken cancel)
    {
        destination = Path.GetFullPath(destination).TrimEnd(Path.DirectorySeparatorChar);
        string parent = Path.GetDirectoryName(destination);
        if (String.IsNullOrEmpty(parent) || destination.Length > 180)
            throw new IOException("Choose a game folder with a shorter path, below a drive's root.");
        if (Directory.Exists(destination) && Directory.GetFileSystemEntries(destination).Length != 0)
            throw new IOException("Choose an empty game folder. Existing games and saves will not be overwritten.");
        // Keep one read-only handle through validation and copying so the disc
        // cannot be replaced or modified between the check and the import.
        using (FileStream iso = new FileStream(isoPath, FileMode.Open, FileAccess.Read, FileShare.Read)) {
            progress(0, "Checking the USA game disc...");
            byte[] image = ValidateIso(iso);
            cancel.ThrowIfCancellationRequested();
            Directory.CreateDirectory(parent);
            DriveInfo drive = new DriveInfo(Path.GetPathRoot(destination));
            if (drive.AvailableFreeSpace < iso.Length + 512L * 1024 * 1024)
                throw new IOException("There is not enough space for the ISO and game files (about 4 GB required).");
            string stage = Path.Combine(parent, ".ac4-install-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(stage);
            bool committed = false;
            try {
                progress(3, "Installing the runtime and shaders...");
                Extract(payload, stage, cancel);
                File.WriteAllBytes(Path.Combine(stage, "runtime", "ps2_image.bin"), image);
                progress(5, "Importing your ISO...");
                iso.Position = 0;
                using (FileStream target = new FileStream(Path.Combine(stage, "game.iso"), FileMode.CreateNew)) {
                    byte[] buffer = new byte[1024 * 1024]; long copied = 0;
                    for (int n; (n = iso.Read(buffer, 0, buffer.Length)) != 0; ) {
                        cancel.ThrowIfCancellationRequested(); target.Write(buffer, 0, n); copied += n;
                        progress(5 + (int)(90 * copied / iso.Length), "Importing your ISO...");
                    }
                    target.Flush(true);
                }
                cancel.ThrowIfCancellationRequested();
                progress(96, "Finishing installation...");
                if (Directory.Exists(destination)) Directory.Delete(destination, false); // empty only
                Directory.Move(stage, destination); committed = true;
                Directory.CreateDirectory(Path.Combine(destination, "saves"));
            }
            finally {
                // Only our freshly-created random staging directory is removed.
                if (!committed && Directory.Exists(stage)) Directory.Delete(stage, true);
            }
        }
        if (!String.IsNullOrEmpty(shortcutPath)) {
            try { CreateShortcut(shortcutPath, destination); }
            catch (Exception ex) {
                throw new IOException("The game is installed at " + destination + ", but the desktop shortcut could not be created. Open Ace Combat 04.exe there. " + ex.Message);
            }
        }
        progress(100, "Installed. Your original ISO has not been changed.");
    }
}
