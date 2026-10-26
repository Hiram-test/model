#include <streambuf> // Access the standard stream buffer API.
#include <typeinfo> // Restrict the compatibility fix to the exact OpenFOAM SHA1 buffer.
#include <cstring> // Compare the exact runtime type name.
#include <dlfcn.h> // Preserve the original behavior for every other stream buffer.
extern "C" int compat_overflow(std::streambuf* self, int character) asm("_ZNSt15basic_streambufIcSt11char_traitsIcEE8overflowEi"); // Interpose only the missing base overflow implementation.
extern "C" int compat_overflow(std::streambuf* self, int character) { // Implement the upstream SHA1 overflow semantics for this legacy binary.
    using traits = std::char_traits<char>; // Use the standard EOF and integer-character conventions.
    const char* name = typeid(*self).name(); // Inspect the actual derived stream-buffer type.
    if (std::strcmp(name, "N4Foam11osha1stream7sha1bufE") == 0) { // Leave all buffers except OpenFOAM1912SHA1 unchanged.
        if (traits::eq_int_type(character, traits::eof())) return traits::not_eof(character); // Do not append an EOF sentinel.
        const char byte = traits::to_char_type(character); // Convert the supplied character without modifying its bytes.
        return self->sputn(&byte, 1) == 1 ? character : traits::eof(); // Delegate hashing to OpenFOAM's existing xsputn implementation.
    } // End the narrowly scoped SHA1 compatibility case.
    using original_type = int (*)(std::streambuf*, int); // Preserve the original library calling convention.
    static auto original = reinterpret_cast<original_type>(dlsym(RTLD_NEXT, "_ZNSt15basic_streambufIcSt11char_traitsIcEE8overflowEi")); // Resolve the unchanged standard-library function.
    return original ? original(self, character) : traits::eof(); // Forward every unrelated stream-buffer operation.
} // This changes no CFD equations, solver tolerances or field values.
