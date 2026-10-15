using System;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal static class InstallerTests
{
    static void Check(bool value, string message) { if (!value) throw new Exception(message); }
    static void Reject(Action action, string message, string reason = null)
    {
        try { action(); } catch (InvalidDataException ex) {
            Check(reason == null || ex.Message.Contains(reason), "Wrong rejection for " + message + ": " + ex.Message);
            return;
        }
        throw new Exception("Accepted " + message);
    }
    static void Put(byte[] b, int offset, uint value) { Array.Copy(BitConverter.GetBytes(value), 0, b, offset, 4); }
    static void Record(byte[] iso, int p, uint sector, uint size, string name)
    {
        byte[] text = Encoding.ASCII.GetBytes(name); iso[p] = (byte)(33 + text.Length + (text.Length % 2 == 0 ? 1 : 0));
        Put(iso, p + 2, sector); Put(iso, p + 10, size); iso[p + 32] = (byte)text.Length;
        Array.Copy(text, 0, iso, p + 33, text.Length);
    }
    static byte[] WrongDisc(bool wrongRegion)
    {
        byte[] iso = new byte[2048 * 1610]; int p = 16 * 2048;
        iso[p] = 1; Array.Copy(Encoding.ASCII.GetBytes("CD001"), 0, iso, p + 1, 5); iso[p + 6] = 1;
        Put(iso, p + 80, 1610); iso[p + 128] = 0; iso[p + 129] = 8;
        Put(iso, p + 158, 20); Put(iso, p + 166, 2048);
        string cnf = "BOOT2 = cdrom0:\\" + (wrongRegion ? "SLES_123.45" : "SLUS_201.52") + ";1\n";
        Array.Copy(Encoding.ASCII.GetBytes(cnf), 0, iso, 21 * 2048, cnf.Length);
        Record(iso, 20 * 2048, 21, (uint)cnf.Length, "SYSTEM.CNF;1");
        Record(iso, 20 * 2048 + iso[20 * 2048], 22, InstallerCore.ElfSize, "SLUS_201.52;1");
        return iso;
    }

    [STAThread]
    static void Main(string[] args)
    {
        if (args.Length == 2 && args[0] == "--preview") { Render(args[1]); return; }
        if (args.Length != 4) throw new Exception("Usage: tests ISO generated-image payload.zip output-folder");
        string output = Path.GetFullPath(args[3]); Directory.CreateDirectory(output);
        Reject(() => InstallerCore.ValidateIso(new MemoryStream(new byte[10])), "short ISO");
        Reject(() => InstallerCore.ValidateIso(new MemoryStream(new byte[2048 * 20])), "non-ISO");
        Reject(() => InstallerCore.ValidateIso(new MemoryStream(WrongDisc(true))), "wrong region");
        Reject(() => InstallerCore.ValidateIso(new MemoryStream(WrongDisc(false))), "changed ELF", "does not match");
        Reject(() => InstallerCore.BuildImage(new byte[52]), "invalid ELF");
        Reject(() => InstallerCore.SafeTarget(output, "../escape.txt"), "payload path traversal");
        using (MemoryStream zipData = new MemoryStream()) {
            using (ZipArchive zip = new ZipArchive(zipData, ZipArchiveMode.Create, true))
                using (StreamWriter writer = new StreamWriter(zip.CreateEntry("../escape.txt").Open())) writer.Write("bad");
            zipData.Position = 0;
            Reject(() => InstallerCore.Extract(zipData, Path.Combine(output, "zip-test"), CancellationToken.None), "ZIP traversal");
        }
        byte[] image;
        using (FileStream iso = File.OpenRead(args[0])) image = InstallerCore.ValidateIso(iso);
        Check(image.SequenceEqual(File.ReadAllBytes(args[1])), "Imported memory image differs from the recompiler");
        Console.WriteLine("ISO checks, modified/wrong-region rejection and exact memory-image comparison passed");

        string protectedFolder = Path.Combine(output, "existing"); Directory.CreateDirectory(protectedFolder);
        File.WriteAllText(Path.Combine(protectedFolder, "keep.txt"), "keep");
        try {
            using (FileStream zip = File.OpenRead(args[2]))
                InstallerCore.Install(args[0], protectedFolder, null, zip, (n, t) => {}, CancellationToken.None);
            throw new Exception("Overwrote an existing folder");
        } catch (IOException) { Check(File.ReadAllText(Path.Combine(protectedFolder, "keep.txt")) == "keep", "Existing data changed"); }

        string cancelled = Path.Combine(output, "cancelled");
        using (CancellationTokenSource token = new CancellationTokenSource())
        using (FileStream zip = File.OpenRead(args[2])) {
            try {
                InstallerCore.Install(args[0], cancelled, null, zip, (n, t) => { if (n >= 10) token.Cancel(); }, token.Token);
                throw new Exception("Cancellation did not stop the copy");
            } catch (OperationCanceledException) {}
        }
        Check(!Directory.Exists(cancelled) && Directory.GetDirectories(output, ".ac4-install-*").Length == 0, "Cancellation left staged data");
        Console.WriteLine("Existing-folder protection and cancelled-copy cleanup passed");

        string installed = Path.Combine(output, "Installed Game");
        string shortcut = Path.Combine(output, "Test Desktop Shortcut.lnk");
        using (FileStream zip = File.OpenRead(args[2]))
            InstallerCore.Install(args[0], installed, shortcut, zip, (n, t) => {}, CancellationToken.None);
        Check(File.Exists(Path.Combine(installed, "runtime", "ac4.exe")), "Runtime not installed");
        Check(File.ReadAllBytes(Path.Combine(installed, "runtime", "ps2_image.bin")).SequenceEqual(image), "Installed image wrong");
        using (FileStream source = File.OpenRead(args[0]))
        using (FileStream target = File.OpenRead(Path.Combine(installed, "game.iso")))
        using (var hash = System.Security.Cryptography.SHA256.Create()) {
            byte[] first = hash.ComputeHash(source), second = hash.ComputeHash(target);
            Check(first.SequenceEqual(second), "Copied ISO differs from source");
        }
        object shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell", true));
        object link = shell.GetType().InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { shortcut });
        string targetPath = (string)link.GetType().InvokeMember("TargetPath", BindingFlags.GetProperty, null, link, null);
        Check(String.Equals(targetPath, Path.Combine(installed, "Ace Combat 04.exe"), StringComparison.OrdinalIgnoreCase), "Shortcut target wrong");
        System.Runtime.InteropServices.Marshal.FinalReleaseComObject(link);
        System.Runtime.InteropServices.Marshal.FinalReleaseComObject(shell);
        Console.WriteLine("Full install, byte-exact ISO copy, generated image and shortcut target passed");

        Render(Path.Combine(output, "setup-preview.png"));
    }

    static void Render(string path)
    {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        using (Setup form = new Setup()) {
            form.StartPosition = FormStartPosition.Manual;
            form.Location = new Point(-32000, -32000);
            form.Show(); Application.DoEvents();
            using (Bitmap bitmap = new Bitmap(form.Width, form.Height)) {
                form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, form.Size));
                bitmap.Save(path);
            }
            form.Hide();
        }
        Console.WriteLine("Installer form rendered");
    }
}
