#!/usr/bin/env python3
"""Detect a repo's shipping targets so an agent can propose a .ship.md.

Prints deploy hosts, migration tools, which database provider each
DATABASE_URL-style variable points at (provider + host only, never
credentials), compose services and matching running containers, a fork's
upstream remote, and mobile release config.

Usage: detect.py [repo_dir] [--json]
Standard library only. Never prints secrets. Missing tools -> "unknown".
"""
import json
import os
import re
import subprocess
import sys
from urllib.parse import urlparse

SKIP_DIRS = {".git", "node_modules", ".next", "dist", "build", ".venv", "venv",
             "__pycache__", ".turbo", ".vercel", "Pods", "DerivedData", ".astro"}
MAX_DEPTH = 3
DB_KEYS = re.compile(r"^(?:export\s+)?([A-Z0-9_]*(?:DATABASE|POSTGRES|DB|MYSQL|MONGO)[A-Z0-9_]*URL[A-Z0-9_]*)\s*=\s*(.+)$")
PROVIDERS = [
    ("neon.tech", "Neon"), ("rlwy.net", "Railway"), ("railway.app", "Railway"),
    ("railway.internal", "Railway"), ("supabase.co", "Supabase"),
    ("supabase.com", "Supabase"), ("pooler.supabase", "Supabase"),
    ("planetscale", "PlanetScale"), ("psdb.cloud", "PlanetScale"),
    ("render.com", "Render"), ("amazonaws.com", "AWS RDS"),
    ("prisma-data.net", "Prisma Postgres"), ("db.prisma.io", "Prisma Postgres"),
    ("turso.io", "Turso"), ("upstash.io", "Upstash"), ("mongodb.net", "MongoDB Atlas"),
    ("xata.sh", "Xata"), ("nhost", "Nhost"), ("fly.dev", "Fly"), ("flycast", "Fly"),
]


def run(cmd, cwd):
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=10)
        return out.stdout if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        depth = os.path.relpath(dirpath, root).count(os.sep)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and depth < MAX_DEPTH]
        yield dirpath, dirnames, filenames


def rel(root, p):
    return os.path.relpath(p, root)


def provider_for(url):
    if url.startswith("file:") or url.endswith(".db") or url.endswith(".sqlite"):
        return "SQLite (file)", "local"
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return "unknown", "unparseable"
    if not host:
        return "unknown", "no host"
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal") or "." not in host:
        return "local / docker", host
    for needle, name in PROVIDERS:
        if needle in host:
            return name, host
    return "other", host


def db_targets(root):
    found = []
    for dirpath, _, filenames in walk(root):
        for f in filenames:
            if not (f == ".env" or f.startswith(".env.")) or f.endswith((".example", ".sample", ".template")):
                continue
            path = os.path.join(dirpath, f)
            try:
                lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
            except OSError:
                continue
            for line in lines:
                m = DB_KEYS.match(line.strip())
                if not m:
                    continue
                val = m.group(2).strip().strip("'\"")
                if not val or val.startswith("${"):
                    continue
                prov, host = provider_for(val)
                found.append({"file": rel(root, path), "var": m.group(1),
                              "provider": prov, "host": host})
    return found


def detect(root):
    r = {"repo": os.path.basename(os.path.abspath(root)), "ship_file": None,
         "deploy": [], "migrations": [], "databases": [], "compose": [],
         "containers": [], "upstream": None, "mobile": [], "scripts": []}
    if os.path.isfile(os.path.join(root, ".ship.md")):
        r["ship_file"] = ".ship.md"

    deploy_markers = {
        "vercel.json": "Vercel", "netlify.toml": "Netlify", "fly.toml": "Fly",
        "railway.json": "Railway", "railway.toml": "Railway",
        "wrangler.toml": "Cloudflare", "wrangler.jsonc": "Cloudflare",
        "render.yaml": "Render", "Procfile": "Heroku-style", "app.yaml": "App Engine",
        "amplify.yml": "AWS Amplify", "serverless.yml": "Serverless",
    }
    compose_names = {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}
    for dirpath, dirnames, filenames in walk(root):
        here = rel(root, dirpath)
        for f in filenames:
            p = os.path.join(here, f) if here != "." else f
            if f in deploy_markers:
                r["deploy"].append({"host": deploy_markers[f], "file": p})
            if f in compose_names:
                r["compose"].append(p)
            if f == "schema.prisma":
                r["migrations"].append({"tool": "Prisma", "file": p,
                                        "deploy_cmd": "prisma migrate deploy"})
            if f.startswith("drizzle.config."):
                r["migrations"].append({"tool": "Drizzle", "file": p,
                                        "deploy_cmd": "drizzle-kit migrate"})
            if f == "alembic.ini":
                r["migrations"].append({"tool": "Alembic", "file": p,
                                        "deploy_cmd": "alembic upgrade head"})
            if f.startswith("knexfile."):
                r["migrations"].append({"tool": "Knex", "file": p,
                                        "deploy_cmd": "knex migrate:latest"})
            if f in ("codemagic.yaml", "codemagic.yml"):
                r["mobile"].append({"tool": "Codemagic", "file": p})
            if f == "eas.json":
                r["mobile"].append({"tool": "EAS", "file": p})
            if f == "Fastfile":
                r["mobile"].append({"tool": "fastlane", "file": p})
            if f == "package.json":
                try:
                    scripts = json.load(open(os.path.join(dirpath, f))).get("scripts", {})
                except (OSError, ValueError):
                    scripts = {}
                for name in scripts:
                    if re.search(r"deploy|migrat|release|db:push|db:deploy", name):
                        r["scripts"].append({"package": p, "script": name})
        if os.path.isfile(os.path.join(dirpath, ".vercel", "project.json")):
            r["deploy"].append({"host": "Vercel (linked)", "file": os.path.join(here, ".vercel/project.json")})
        if here.endswith(os.path.join("supabase", "migrations")) or here == os.path.join("supabase", "migrations"):
            r["migrations"].append({"tool": "Supabase", "file": here, "deploy_cmd": "supabase db push"})
        elif os.path.basename(dirpath) == "migrations" and any(f.endswith(".sql") for f in filenames) \
                and not any(m["file"].startswith(os.path.dirname(here)) for m in r["migrations"] if os.path.dirname(here)):
            r["migrations"].append({"tool": "SQL files", "file": here,
                                    "deploy_cmd": "see package scripts (db:migrate / migrate)"})
        if any(f.endswith(".xcodeproj") for f in dirnames):
            r["mobile"].append({"tool": "Xcode project", "file": here})

    r["databases"] = db_targets(root)

    remotes = run(["git", "remote", "-v"], root) or ""
    for line in remotes.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "upstream":
            r["upstream"] = re.sub(r"https://[^@/]+@", "https://", parts[1])
            break

    if r["compose"]:
        ps = run(["docker", "ps", "--format", "{{json .}}"], root)
        if ps is None:
            r["containers"] = "unknown (docker not available)"
        else:
            name = r["repo"].lower().replace(" ", "")
            for line in ps.splitlines():
                try:
                    c = json.loads(line)
                except ValueError:
                    continue
                labels = c.get("Labels", "")
                if name in c.get("Names", "").lower() or name in labels.lower():
                    r["containers"].append({"name": c.get("Names"), "image": c.get("Image"),
                                            "status": c.get("Status")})
    return r


def human(r):
    out = [f"repo: {r['repo']}", f"ship file: {r['ship_file'] or 'none'}"]
    def section(title, items, fmt):
        out.append(f"\n{title}:")
        if not items:
            out.append("  (none found)")
        elif isinstance(items, str):
            out.append(f"  {items}")
        else:
            out.extend("  - " + fmt(i) for i in items)
    section("deploy", r["deploy"], lambda i: f"{i['host']}  ({i['file']})")
    section("migrations", r["migrations"], lambda i: f"{i['tool']}  ({i['file']}) -> {i['deploy_cmd']}")
    section("database targets (provider / host only)", r["databases"],
            lambda i: f"{i['var']} in {i['file']}: {i['provider']} [{i['host']}]")
    section("compose files", r["compose"], lambda i: i)
    section("matching running containers", r["containers"],
            lambda i: f"{i['name']}  {i['image']}  {i['status']}")
    out.append(f"\nupstream remote: {r['upstream'] or 'none'}")
    section("mobile release", r["mobile"], lambda i: f"{i['tool']}  ({i['file']})")
    section("package scripts", r["scripts"], lambda i: f"{i['package']}: {i['script']}")
    provs = {d["provider"] for d in r["databases"]}
    if len(provs) > 1:
        out.append("\nWARNING: env files point at more than one database provider: "
                   + ", ".join(sorted(provs)) + ". Confirm the production target before migrating.")
    return "\n".join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = args[0] if args else (run(["git", "rev-parse", "--show-toplevel"], ".") or ".").strip()
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        sys.exit(2)
    r = detect(root)
    print(json.dumps(r, indent=2) if "--json" in sys.argv else human(r))


if __name__ == "__main__":
    main()
