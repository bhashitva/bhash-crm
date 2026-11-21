#!/bin/sh
set -eu
cd "$(dirname "$0")"
version=0.28.0
checksum=8fbcef3abb5a56f0a13d41c0d66cdcae00dfc2656f481f578d97d82cd0863fd0
compiler="target/bhash-compiler-$version.jar"
mkdir -p target
if [ ! -f "$compiler" ]; then
    curl --fail --location --retry 3 "https://github.com/bhashitva/bhash/releases/download/bhash-$version/bhash-compiler-$version.jar" -o "$compiler.download"
    printf '%s  %s\n' "$checksum" "$compiler.download" | sha256sum -c -
    mv "$compiler.download" "$compiler"
fi
printf '%s  %s\n' "$checksum" "$compiler" | sha256sum -c -
java tools/GenerateSourceCatalog.java
java -jar "$compiler" deps verify .
java -jar "$compiler" compile . --target jvm -o target/crm.jar
