/* Constant for the mach_header size (32-bit architectures) */
const MH_FIELDS = 7;
export const MH_HEADER_SIZE = MH_FIELDS * 4;

/* Constant for the mach_header size (64-bit architectures) */
const MH_FIELDS_64 = 8;
export const MH_HEADER_SIZE_64 = MH_FIELDS_64 * 4;

/* Constant for the magic field of the mach_header (32-bit architectures) */
export const MH_MAGIC = 0xfeedface/* the mach magic number */

/* Constant for the magic field of the mach_header_64 (64-bit architectures) */
export const MH_MAGIC_64 = 0xfeedfacf /* the 64-bit mach magic number */

/*
 * The 64-bit (32-bit) mach header appears at the very beginning of object files for
 * 64-bit (32-bit) architectures.
 */
export class MachOHeader {
    public readonly magic: number;          /* mach magic number identifier */
    public readonly cputype: number;        /* cpu specifier */
    public readonly cpusubtype: number;     /* machine specifier */
    public readonly filetype: number;       /* type of file */
    public readonly ncmds: number;          /* number of load commands */
    public readonly sizeofcmds: number;     /* the size of all the load commands */
    public readonly flags: number;          /* flags */
    public readonly reserved?: number;       /* reserved */

    constructor(module: Buffer) {
        this.magic = module.readUint32LE(0);
        this.cputype = module.readInt32LE(4);
        this.cpusubtype = module.readInt32LE(8);
        this.filetype = module.readUint32LE(12);
        this.ncmds = module.readUint32LE(16);
        this.sizeofcmds = module.readUint32LE(20);
        this.flags = module.readUint32LE(24);
        if (MH_MAGIC_64 === this.magic) this.reserved = module.readUint32LE(28);
    }
}