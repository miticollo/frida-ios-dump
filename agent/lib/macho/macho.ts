import { Buffer } from 'node:buffer';
import assert from 'node:assert';
import {
    MachOHeader,
    MH_HEADER_SIZE,
    MH_HEADER_SIZE_64,
    MH_MAGIC_64
} from "./header.js";
import { LoadCommand } from './commands/command.js';
import { LoadCommandFactory } from './commands/factory.js';

export class MachO {
    public readonly header: MachOHeader;
    public readonly loadCommands: LoadCommand[] = [];
    public readonly module: Buffer;
    public readonly base: NativePointer;

    constructor(module: ArrayBuffer) {
        this.module = Buffer.from(module);
        this.base = module.unwrap();
        this.header = new MachOHeader(this.module);
        this.parseLoadCommands();
    }

    public is64(): boolean {
        return this.header.magic === MH_MAGIC_64;
    }

    private parseLoadCommands(): void {
        const headerSize: number = this.is64() ? MH_HEADER_SIZE_64 : MH_HEADER_SIZE;
        const end: number = headerSize + this.header.sizeofcmds;
        for (let offset = headerSize; offset < end;) {
            const command: LoadCommand = LoadCommandFactory.retrieveCommand(this.module, offset, this.base);
            this.loadCommands.push(command);
            offset += command.cmdsize;
        }
        assert(this.loadCommands.length === this.header.ncmds, new Error(`loadCommands.length !== ncmds: ${this.loadCommands.length} !== ${this.header.ncmds}`));
    }
}