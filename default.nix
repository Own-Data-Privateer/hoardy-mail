with import <nixpkgs> {};
with python3Packages;

buildPythonApplication rec {
  pname = "imaparms";
  version = "1.1";
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

  nativeBuildInputs = [
    mypy
  ];
}
