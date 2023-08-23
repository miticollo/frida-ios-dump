/* Constants for the cmd field of all load commands, the type */
export const LC_ENCRYPTION_INFO = 0x21              /* encrypted segment information */
export const LC_ENCRYPTION_INFO_64 = 0x2C           /* 64-bit encrypted segment information */

/*
 * The load commands directly follow the mach_header.  The total size of all
 * of the commands is given by the sizeofcmds field in the mach_header.  All
 * load commands must have as their first two fields cmd and cmdsize.  The cmd
 * field is filled in with a constant for that command type.  Each command type
 * has a structure specifically for it.  The cmdsize field is the size in bytes
 * of the particular load command structure plus anything that follows it that
 * is a part of the load command (i.e. section structures, strings, etc.).  To
 * advance to the next load command the cmdsize can be added to the offset or
 * pointer of the current load command.  The cmdsize for 32-bit architectures
 * MUST be a multiple of 4 bytes and for 64-bit architectures MUST be a multiple
 * of 8 bytes (these are forever the maximum alignment of any load commands).
 * The padded bytes must be zero.  All tables in the object file must also
 * follow these rules so the file can be memory mapped.  Otherwise the pointers
 * to these tables will not work well or at all on some machines.  With all
 * padding zeroed like objects will compare byte for byte.
 */
export class LoadCommand {
    public readonly base: NativePointer;
    public readonly cmd: number;             /* type of load command */
    public readonly cmdsize: number;         /* total size of command in bytes */

    constructor(cmd: number, module: Buffer, offset: number, base: NativePointer) {
        this.base = base;
        this.cmd = cmd;
        this.cmdsize = module.readUint32LE(offset);
    }
}