import { LoadCommand } from './command.js';

/*
 * The encryption_info_command contains the file offset and size of an
 * encrypted segment.
 */
export class EncryptionInfo extends LoadCommand {
    public readonly cryptoff: number;        /* file offset of encrypted range */
    public readonly cryptsize: number;       /* file size of encrypted range */
    public readonly cryptid: number;         /* which encryption system, 0 means not-encrypted yet */

    constructor(cmd: number, module: Buffer, offset: number, base: NativePointer) {
        super(cmd, module, offset, base);
        this.cryptoff = module.readUint32LE(offset + 4);
        this.cryptsize = module.readUint32LE(offset + 8);
        this.cryptid = module.readUint32LE(offset + 12);
    }

    public isEncrypted(): boolean {
        return this.cryptid === 1;
    }
}

/*
 * The encryption_info_command_64 contains the file offset and size of an
 * encrypted segment (for use in x86_64 targets).
 */
export class EncryptionInfo64 extends EncryptionInfo {
    public readonly pad: number;             /* padding to make this struct's size a multiple of 8 bytes */

    constructor(cmd: number, module: Buffer, offset: number, base: NativePointer) {
        super(cmd, module, offset, base);
        this.pad = module.readUint32LE(offset + 16);
    }
}