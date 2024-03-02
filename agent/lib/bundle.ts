import { NSBundle, NSDictionary } from './types.js';
import { manager } from './shared.js';

function infoDictionaryForPath(path: ObjC.Object): ObjC.Object | null {
    const infoPlistPath = path['stringByAppendingPathComponent_']("Info.plist");
    if (!manager['fileExistsAtPath_'](infoPlistPath))
        return null;
    const info = NSDictionary['dictionaryWithContentsOfFile_'](infoPlistPath);
    if (!info)
        throw new Error(`"${infoPlistPath}" is not valid plist format`)
    return info;
}

export function loadBundle(path: ObjC.Object, error: NativePointer): boolean {
    const dict: ObjC.Object | null = infoDictionaryForPath(path);
    if (dict !== null && dict['objectForKey_']("CFBundleExecutable")) {
        const bundle: ObjC.Object = NSBundle['bundleWithPath_'](path);
        return bundle['isLoaded']() ? true : bundle['loadAndReturnError_'](error);
    }
    return true; // ignore this bundle
}