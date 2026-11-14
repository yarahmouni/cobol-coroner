# S0 checklist (macOS)

1. Register for Kiroween: https://kiroween.devpost.com
2. Create the public repo `yarahmouni/cobol-lazarus`, license Apache-2.0, then upload this folder: https://github.com/new
3. Install Kiro: https://kiro.dev/downloads
4. Install Docker Desktop: https://www.docker.com/products/docker-desktop/
5. Install Homebrew if missing: https://brew.sh
6. Install GnuCOBOL: `brew install gnucobol` then `cobc --version` (expect 3.2): https://formulae.brew.sh/formula/gnucobol
7. Install JDK 17 (Temurin): https://adoptium.net/temurin/releases/?version=17
8. Install Python 3.12: https://www.python.org/downloads/
9. Open the repo in Kiro, then create a spec from `.kiro/specs/s0-toolchain/requirements.md` and let Kiro generate `design.md` and `tasks.md`.
10. Run the S0 tasks in Kiro. Report results here: trace with line numbers yes or no, `mcp.json` content that works.
11. Request Kiro credits as soon as the form is available (before 1 Dec, 21:00 Paris): https://kiroween.devpost.com/updates
