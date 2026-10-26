#include <streambuf> // Reproduce the legacy base-overflow behavior.
#include <sstream> // Verify ordinary string streams remain unchanged.
#include <iostream> // Report the compatibility contract.
#include <string> // Retain the exact appended byte sequence.
namespace Foam { class osha1stream { public: class sha1buf : public std::streambuf { // Match the exact legacy type identity, without linking solver internals.
public: std::string appended; // Observe which bytes reach the original append path.
protected: std::streamsize xsputn(const char* bytes, std::streamsize length) override { appended.append(bytes, static_cast<std::size_t>(length)); return length; } // Preserve the native unbuffered-write pattern.
}; }; } // Intentionally leave overflow absent, as in the affected OpenFOAM1912 class.
int main() { // Exercise both the affected and unaffected stream classes.
    Foam::osha1stream::sha1buf buffer; // Construct the exact affected type.
    std::ostream stream(&buffer); // Use the standard C++ output interface.
    stream.put('a'); stream.write("bc", 2); // Mix single-byte and bulk writes as dictionary hashing does.
    if (!stream.good() || buffer.appended != "abc") return 1; // Reject lost or duplicated bytes.
    std::ostringstream ordinary; ordinary << "ordinary" << 42; // Exercise an unrelated standard stream.
    if (ordinary.str() != "ordinary42") return 2; // Verify ordinary streams retain their behavior.
    std::streambuf* raw = new std::stringbuf; raw->sputn("untouched", 9); delete raw; // Verify normal virtual destruction and bulk writes.
    std::cout << "PASS: exact legacy buffer receives abc; ordinary streams unchanged\n"; // Record the compatibility invariant.
    return 0; // Signal a successful regression check.
} // This test contains no CFD physics or convergence controls.
