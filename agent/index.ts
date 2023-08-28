import { dlopen, RTLD_GLOBAL, RTLD_LAZY } from "./lib/dlopen.js";
import { loadBundle } from "./lib/bundle.js";
import { appPath, manager } from "./lib/shared.js";
import { MachO } from "./lib/macho/macho.js";
import { LoadCommand } from "./lib/macho/commands/command.js";
import { EncryptionInfo, EncryptionInfo64 } from "./lib/macho/commands/encryption_info.js";
import assert from "node:assert";
import { NSBundle } from "./lib/types.js";

/* ObjC.available is buggy on non-objc apps, so override this */
const ObjCAvailable: boolean = (Process.platform === 'darwin') && !(Java && Java.available) && ObjC && ObjC.available && ObjC.classes && typeof ObjC.classes.NSString !== 'undefined';
if (!ObjCAvailable) throw new Error('This tool requires the objc runtime');

const payloadPath: string = appPath.UTF8String().match(/^\/private\/var\/containers\/Bundle\/Application\/[A-F0-9-]+/)[0];

function loadDynamicLibraries(path: ObjC.Object): void {
    const files = manager.contentsOfDirectoryAtPath_error_(path, NULL);
    const count = files.count().valueOf();
    for (let i = 0; i !== count; i++) {
        const file = files.objectAtIndex_(i);
        const fullPath = path.stringByAppendingPathComponent_(file);
        const remotePath: string = fullPath.UTF8String().replace(payloadPath, "").substring(1);

        const isDir: NativePointer = Memory.alloc(Process.pointerSize);
        manager.fileExistsAtPath_isDirectory_(fullPath, isDir);

        if (! isDir.readPointer().isNull()) {
            if (file.UTF8String() !== '_CodeSignature' && file.UTF8String() !== 'SC_Info') {
                if (file.toString().endsWith(".framework")
                    || file.toString().endsWith(".bundle")
                    || file.toString().endsWith(".xctest")) {
                    const errorPtr: NativePointer = Memory.alloc(Process.pointerSize);
                    errorPtr.writePointer(NULL);
                    if (!loadBundle(fullPath, errorPtr)) {
                        const error: ObjC.Object = new ObjC.Object(errorPtr.readPointer());
                        throw new Error(`${error.userInfo().objectForKey_("NSLocalizedDescription")}`);
                    }
                }
                send({
                    type: "directory",
                    path: remotePath,
                });
                loadDynamicLibraries(fullPath);
            }
        } else {
            if (file.toString().endsWith(".dylib")) {
                const modules: Module[] = Process.enumerateModules().filter((m: Module): boolean => m.path.indexOf(fullPath.UTF8String()) !== -1);
                if (modules.length === -1)
                    if (dlopen(fullPath.toString(), RTLD_GLOBAL | RTLD_LAZY).isNull())
                        throw new Error(`${file.toString()} @ ${path.toString()} is not loaded`);
            }
            send({
                type: "file",
                path: remotePath,
            }, File.readAllBytes(fullPath.UTF8String()));
        }
    }
}

function dumpModule(module: Module): void {
    const candidates: Module[] = Process.enumerateModules().filter((x: Module): boolean => x.name === module.name);
    if (candidates.length !== 1) throw new Error(`Cannot find Mach-O: ${module.path}`);

    const patchedModule: MachO = new MachO(File.readAllBytes(module.path));

    patchedModule.loadCommands.forEach((command: LoadCommand): void => {
        if (command instanceof EncryptionInfo64 || command instanceof EncryptionInfo)
            if ((command as EncryptionInfo).isEncrypted()) {

                console.log(`\nDumping ${module.name}...`);

                /* Great! node:Buffer and ArrayBuffer share memory */
                patchedModule.module.writeUInt32LE(0, command.base.add(16).sub(patchedModule.base).toUInt32());
                assert((patchedModule.base.add(command.base.add(16).sub(patchedModule.base).toUInt32()).readU32() >>> 0) === 0, new Error("cryptid is not properly set"));

                console.log(` - Changed \`cryptid\` from 1 to 0`);

                assert((module.base.add(command.base.add(16).sub(patchedModule.base).toUInt32()).readU32() >>> 0) === 1, new Error("Fields between Module and Mach-O file don't match"));

                console.log(` - Encrypted data are replaced using the same module in memory`);

                const plainBuffer: ArrayBuffer = module.base.add(command.cryptoff).readByteArray(command.cryptsize)!;
                patchedModule.base.add(command.cryptoff).writeByteArray(plainBuffer);

                console.log(" - Sending module to PC/macOS... ");

                send({
                    type: "file",
                    mode: "executable",
                    path: module.path.replace(payloadPath, "").substring(1),
                }, patchedModule.module.buffer as ArrayBuffer);
            }
    });
}

send({
    type: "info",
    bundleId: NSBundle.mainBundle().bundleIdentifier().toString(),
    version: NSBundle.mainBundle().infoDictionary().objectForKey_("CFBundleShortVersionString").toString(),
});

send({
    type: "directory",
    path: appPath.UTF8String().replace(payloadPath, "").substring(1),
});

loadDynamicLibraries(appPath);
Process.enumerateModules()
    .filter((x: Module) => x.path.startsWith(appPath.UTF8String()))
    .forEach((module: Module): void => dumpModule(module));
