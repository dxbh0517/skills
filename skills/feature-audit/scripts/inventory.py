#!/usr/bin/env python3
"""List an app's routes, API endpoints, jobs, and tables for a feature audit.

Usage: inventory.py [app_dir] [--json]
Standard library only. Reads files; runs nothing; never prints env values.
"""
import json
import os
import re
import sys

SKIP = {".git", "node_modules", ".next", "dist", "build", ".venv", "venv", "__pycache__",
        ".turbo", ".vercel", ".svelte-kit", ".astro", "coverage", "Pods", ".output"}
PAGE_EXT = (".tsx", ".jsx", ".ts", ".js", ".mdx", ".astro", ".svelte", ".vue")
SERVER_EXT = (".ts", ".js", ".mjs", ".cjs", ".py")
HTTP = re.compile(r"""\b(?:app|router|api|server|r|route|hono)\.(get|post|put|patch|delete)\(\s*['"`]([^'"`]+)""", re.I)
FASTAPI = re.compile(r"""@\w+\.(get|post|put|patch|delete)\(\s*['"]([^'"]+)""")
NEST_CTRL = re.compile(r"""@Controller\(\s*(?:['"`]([^'"`]*)['"`]|\{[^}]*path:\s*['"`]([^'"`]*)['"`])?""")
NEST_ROUTE = re.compile(r"""@(Get|Post|Put|Patch|Delete)\(\s*(?:['"`]([^'"`]*)['"`])?\s*\)""")
NEXT_METHODS = re.compile(r"export\s+(?:async\s+)?(?:function|const)\s+(GET|POST|PUT|PATCH|DELETE)\b")
PRISMA_MODEL = re.compile(r"^model\s+(\w+)\s*\{", re.M)
SQL_TABLE = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?[\"`]?(?:\w+\.)?[\"`]?(\w+)", re.I)
DRIZZLE = re.compile(r"""(?:pgTable|sqliteTable|mysqlTable)\(\s*['"](\w+)""")


def files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")]
        for f in filenames:
            yield os.path.join(dirpath, f)


def read(p, limit=400_000):
    try:
        with open(p, encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def clean_segments(parts):
    out = []
    for s in parts:
        if s.startswith("(") and s.endswith(")"):
            continue  # Next.js route groups
        if s.startswith("@"):
            continue  # parallel route slots
        if s.startswith("_"):
            return None  # private folders
        out.append(s)
    return out


def route_from(path, base):
    rel = os.path.relpath(path, base)
    parts = rel.split(os.sep)
    name = os.path.splitext(parts[-1])[0]
    segs = clean_segments(parts[:-1])
    if segs is None:
        return None
    return segs, name


def scan(root):
    inv = {"pages": [], "api": [], "jobs": [], "tables": [], "frameworks": set()}
    seen_tables = set()
    sql_seen, sql_tables = set(), []
    for p in files(root):
        rel = os.path.relpath(p, root)
        parts = rel.split(os.sep)
        fname = parts[-1]

        # Next.js app router
        if "app" in parts and fname.split(".")[0] in ("page", "route") and fname.endswith(PAGE_EXT):
            i = len(parts) - 1 - parts[::-1].index("app")
            r = route_from(p, os.path.join(root, *parts[: i + 1]))
            if r:
                segs, name = r
                url = "/" + "/".join(segs)
                if name == "page":
                    inv["frameworks"].add("Next.js app router")
                    inv["pages"].append({"route": url, "file": rel})
                else:
                    methods = sorted(set(NEXT_METHODS.findall(read(p)))) or ["?"]
                    inv["api"].append({"route": url, "methods": methods, "file": rel})
            continue

        # Next.js pages router / Astro
        if "pages" in parts and fname.endswith(PAGE_EXT) and "components" not in parts:
            i = len(parts) - 1 - parts[::-1].index("pages")
            r = route_from(p, os.path.join(root, *parts[: i + 1]))
            if r and not r[1].startswith("_"):
                segs, name = r
                is_api = bool(segs) and segs[0] == "api"
                url = "/" + "/".join(segs + ([] if name == "index" else [name]))
                if fname.endswith(".astro"):
                    inv["frameworks"].add("Astro")
                elif fname.endswith((".ts", ".js")) and not is_api:
                    inv["frameworks"].add("Astro")  # Astro endpoints
                    is_api = True
                else:
                    inv["frameworks"].add("Next.js pages router" if not fname.endswith((".vue",)) else "Nuxt")
                if is_api:
                    inv["api"].append({"route": url, "methods": sorted(set(NEXT_METHODS.findall(read(p)))) or ["?"], "file": rel})
                else:
                    inv["pages"].append({"route": url, "file": rel})
            continue

        # SvelteKit (+page / +server) and Remix / React Router flat routes
        if "routes" in parts and fname.endswith(PAGE_EXT) and "components" not in parts:
            i = len(parts) - 1 - parts[::-1].index("routes")
            r = route_from(p, os.path.join(root, *parts[: i + 1]))
            if r:
                segs, name = r
                if name.startswith("+page"):
                    inv["frameworks"].add("SvelteKit")
                    inv["pages"].append({"route": "/" + "/".join(segs), "file": rel})
                elif name.startswith("+server"):
                    inv["frameworks"].add("SvelteKit")
                    inv["api"].append({"route": "/" + "/".join(segs), "methods": sorted(set(NEXT_METHODS.findall(read(p)))) or ["?"], "file": rel})
                elif not name.startswith("+") and parts[i - 1:i] == ["app"]:
                    inv["frameworks"].add("Remix / React Router")
                    pieces = [x for x in name.split(".") if x not in ("_index", "route")]
                    route = "/" + "/".join(segs + [x for x in pieces if not x.startswith("_")])
                    inv["pages"].append({"route": route.replace("$", ":"), "file": rel})
            continue

        if fname.endswith(SERVER_EXT) and not fname.endswith((".test.ts", ".spec.ts", ".d.ts")):
            text = read(p)
            for m, route in HTTP.findall(text) + FASTAPI.findall(text):
                if route.startswith("/"):
                    inv["api"].append({"route": route, "methods": [m.upper()], "file": rel})
            ctrl = NEST_CTRL.search(text)
            if ctrl:
                inv["frameworks"].add("NestJS")
                prefix = (ctrl.group(1) or ctrl.group(2) or "").strip("/")
                for m, sub in NEST_ROUTE.findall(text):
                    route = "/" + "/".join(x for x in (prefix, (sub or "").strip("/")) if x)
                    inv["api"].append({"route": route, "methods": [m.upper()], "file": rel})
            for t in DRIZZLE.findall(text):
                if t not in seen_tables:
                    seen_tables.add(t)
                    inv["tables"].append({"table": t, "file": rel})
            if re.search(r"\b(new\s+Worker\(|cron\.schedule\(|schedule\(['\"]|\.process\(|defineJob|inngest\.createFunction|createFunction\()", text) and "/node_modules/" not in p:
                inv["jobs"].append({"job": os.path.splitext(fname)[0], "file": rel, "source": "code"})

        if fname == "schema.prisma":
            for t in PRISMA_MODEL.findall(read(p)):
                if t not in seen_tables:
                    seen_tables.add(t)
                    inv["tables"].append({"table": t, "file": rel})
        if fname.endswith(".sql"):
            for t in SQL_TABLE.findall(read(p)):
                if t not in sql_seen:
                    sql_seen.add(t)
                    sql_tables.append({"table": t, "file": rel})
        if fname == "vercel.json":
            try:
                for c in json.loads(read(p)).get("crons", []):
                    inv["jobs"].append({"job": c.get("path"), "file": rel, "source": "vercel cron " + c.get("schedule", "")})
            except ValueError:
                pass

    if not inv["tables"]:
        inv["tables"] = sql_tables  # raw SQL only when there is no ORM schema
    # Framework labels from config files beat guesses from folder layout.
    configs = {"next.config": "Next.js", "astro.config": "Astro", "svelte.config": "SvelteKit",
               "remix.config": "Remix", "react-router.config": "React Router", "nuxt.config": "Nuxt",
               "nest-cli.json": "NestJS"}
    found = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")]
        if os.path.relpath(dirpath, root).count(os.sep) > 2:
            dirnames[:] = []
        for f in filenames:
            for k, v in configs.items():
                if f.startswith(k):
                    found.add(v)
    if found:
        inv["frameworks"] = found
    # de-duplicate
    for k, key in (("pages", "route"), ("api", "route")):
        uniq = {}
        for row in inv[k]:
            uniq.setdefault((row[key], row["file"]), row)
        inv[k] = sorted(uniq.values(), key=lambda r: r[key])
    inv["frameworks"] = sorted(inv["frameworks"])
    return inv


def markdown(inv):
    out = [f"Frameworks: {', '.join(inv['frameworks']) or 'unknown'}", ""]
    out += [f"## Pages ({len(inv['pages'])})", "", "| Route | File |", "| --- | --- |"]
    out += [f"| `{r['route']}` | {r['file']} |" for r in inv["pages"]]
    out += ["", f"## API ({len(inv['api'])})", "", "| Route | Methods | File |", "| --- | --- | --- |"]
    out += [f"| `{r['route']}` | {', '.join(r.get('methods', ['?']))} | {r['file']} |" for r in inv["api"]]
    out += ["", f"## Jobs ({len(inv['jobs'])})", ""]
    out += [f"- {j['job']} ({j['source']}) — {j['file']}" for j in inv["jobs"]] or ["(none found)"]
    out += ["", f"## Tables ({len(inv['tables'])})", ""]
    out += [", ".join(t["table"] for t in inv["tables"]) or "(none found)"]
    return "\n".join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = args[0] if args else "."
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        sys.exit(2)
    inv = scan(root)
    print(json.dumps(inv, indent=2) if "--json" in sys.argv else markdown(inv))


if __name__ == "__main__":
    main()
