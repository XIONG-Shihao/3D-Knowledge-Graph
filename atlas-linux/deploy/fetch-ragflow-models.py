"""Download pinned DeepDoc/Chinese tokenizer assets for the native RAGFlow profile."""

import argparse
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    import nltk
    from huggingface_hub import snapshot_download

    root = args.root
    target = root / "rag/res/deepdoc"
    target.mkdir(parents=True, exist_ok=True)
    versions = json.loads(args.manifest.read_text())
    for repo, revision in versions["model_revisions"].items():
        snapshot = Path(snapshot_download(repo, revision=revision))
        if repo.endswith("/huqie"):
            shutil.copy2(snapshot / "huqie.txt.trie", root / "rag/res/huqie.txt.trie")
        else:
            for file in snapshot.rglob("*"):
                if file.is_file() and ".cache" not in file.parts and not file.name.startswith("."):
                    shutil.copy2(file, target / file.name)
    nltk_dir = root / "nltk_data"
    for dataset in ["wordnet", "punkt", "punkt_tab"]:
        if not nltk.download(dataset, download_dir=str(nltk_dir), raise_on_error=True):
            raise RuntimeError(f"NLTK asset download failed: {dataset}")
    # The optional Office parser uses Tika. Check the upstream SHA-512 before use.
    filename = "tika-server-standard-3.0.0.jar"
    url = (
        "https://repo.maven.apache.org/maven2/org/apache/tika/tika-server-standard/3.0.0/"
        + filename
    )
    urllib.request.urlretrieve(url, root / filename)
    with urllib.request.urlopen(url + ".sha512") as response:
        expected = response.read().decode().strip().split()[0]
    actual = hashlib.sha512((root / filename).read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError("Tika checksum verification failed.")
    (root / (filename + ".md5")).write_text(hashlib.md5((root / filename).read_bytes()).hexdigest())
    print("Pinned document models, Chinese tokenizer, and Tika downloaded.")


if __name__ == "__main__":
    main()
