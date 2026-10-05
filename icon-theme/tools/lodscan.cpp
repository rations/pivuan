// lodscan: for each Icon-O-Matic file, count the shapes that Haiku draws only at
// some sizes (a visibility range other than "always"), and the ones drawn only
// at small sizes. Files hvif-tools cannot read are listed as FAIL.
//
// Usage: lodscan <iom-file>...     (make lodscan runs it on Haiku's artwork)
#include "IOMParser.h"
#include <cstdio>
int main(int argc, char** argv) {
	for (int a = 1; a < argc; ++a) {
		iom::IOMParser p;
		if (!p.ParseFile(argv[a])) { printf("FAIL %s %s\n", argv[a], p.GetLastError().c_str()); continue; }
		const iom::Icon& icon = p.GetIcon();
		int lod = 0, small = 0;
		for (const auto& s : icon.shapes) {
			if (s.minVisibility > 0.0f || s.maxVisibility < 3.99f) ++lod;
			if (s.maxVisibility < 3.99f) ++small;
		}
		printf("%s shapes=%zu lod=%d smallonly=%d\n", argv[a], icon.shapes.size(), lod, small);
	}
}
