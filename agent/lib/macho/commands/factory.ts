import { LC_ENCRYPTION_INFO, LC_ENCRYPTION_INFO_64, LoadCommand } from './command.js';
import { EncryptionInfo, EncryptionInfo64 } from './encryption_info.js';

export class LoadCommandFactory {
    private constructor() {
        // Empty body
    }

    public static retrieveCommand(module: Buffer, offset: number, base: NativePointer): LoadCommand {
        const cmd: number = module.readUint32LE(offset);
        const cmdBase: NativePointer = base.add(offset);

        switch (cmd) {
            case LC_ENCRYPTION_INFO:
                return new EncryptionInfo(cmd, module, offset + 4, cmdBase);
            case LC_ENCRYPTION_INFO_64:
                return new EncryptionInfo64(cmd, module, offset + 4, cmdBase);
            default:
                return new LoadCommand(cmd, module, offset + 4, cmdBase);
        }
    }
}