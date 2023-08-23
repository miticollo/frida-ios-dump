export const RTLD_GLOBAL = 0x8;
export const RTLD_LAZY = 0x1;

const _dlopen = new NativeFunction(Module.getExportByName('/usr/lib/system/libdyld.dylib', 'dlopen'), 'pointer', ['pointer', 'int']);

export function dlopen(library: string, mode: number): NativePointer {
  const path: NativePointer = Memory.allocUtf8String(library);
  return _dlopen(path, mode);
}