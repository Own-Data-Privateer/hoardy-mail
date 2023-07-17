with import <nixpkgs> {};
with python3Packages;

buildPythonApplication rec {
  pname = "pyimapexpire";
  version = "1.0";
  disabled = !isPy3k;

  src = lib.cleanSourceWith {
    src = ./.;
    filter = name: type: let baseName = baseNameOf (toString name); in
      lib.cleanSourceFilter name type && ! (
        (baseName == "default.nix") ||
        (baseName == "result") ||
        (baseName == "results") ||
        (baseName == "__pycache__")
      );
  };
}
