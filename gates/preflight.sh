#!/bin/bash
# preflight.sh — mechanical checks in one command. Zero tokens, seconds to run.
#
# Replaces several expensive LLM audit passes: everything that a grep can verify is verified
# by a grep. Run from the project root (where the .xcodeproj lives):
#     bash $PIPELINE_ROOT/gates/preflight.sh
#
# Exit: 0 — clean, 1 — findings (printed). Every FAIL blocks handoff; every warn gets a look.
# Each check exists because an agent produced that exact defect at least once.

fails=0
warns=0

say()  { printf '\n\033[1m%s\033[0m\n' "$1"; }
ok()   { printf '  ok    %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fails=$((fails+1)); }
warn() { printf '  warn  %s\n' "$1"; warns=$((warns+1)); }

SRC=$(find . -maxdepth 2 -name "*.xcodeproj" | head -1 | xargs dirname 2>/dev/null)
[ -z "$SRC" ] && SRC="."
APP=$(find "$SRC" -maxdepth 1 -type d ! -name "*.xcodeproj" ! -name "." | head -1)
[ -z "$APP" ] && APP="$SRC"

say "1. Completeness — stubs, placeholders, crash sources"
# Agents leave "TODO" and "not implemented" behind when they silently narrow scope.
if grep -rqniE "lorem ipsum|placeholder text|coming soon…|not implemented|TODO:|FIXME" --include="*.swift" "$APP" 2>/dev/null; then
  bad "stubs/TODO found"; grep -rniE "lorem ipsum|placeholder text|not implemented|TODO:|FIXME" --include="*.swift" "$APP" | head -5
else ok "no stubs or TODO"; fi

# Force unwraps crash under a reviewer's rough testing.
FORCE='as! |try! |[a-zA-Z0-9_\]]!\.|[a-zA-Z0-9_]!\)|= *[a-zA-Z0-9_.]+!$'
if grep -rqnE "$FORCE" --include="*.swift" "$APP" 2>/dev/null; then
  warn "force unwrap / force cast present — review each"; grep -rnE "$FORCE" --include="*.swift" "$APP" | head -5
else ok "no force unwraps"; fi

say "2. Accurate metadata"
if grep -rqniE '"[^"]*\b(beta|alpha|trial version|demo version)\b' --include="*.swift" "$APP" 2>/dev/null; then
  bad "beta/alpha/trial wording in UI"; else ok "no beta/alpha/trial in UI"; fi

VER=$(grep -m1 "MARKETING_VERSION" "$SRC"/*.xcodeproj/project.pbxproj 2>/dev/null | sed 's/.*= *//;s/;//')
case "$VER" in
  0.*) bad "MARKETING_VERSION = $VER — 0.x reads as an unfinished product" ;;
  "")  warn "MARKETING_VERSION not found" ;;
  *)   ok "MARKETING_VERSION = $VER" ;;
esac

if grep -rqn '"[0-9]\+\.[0-9]\+\.[0-9]\+"' --include="*.swift" "$APP" 2>/dev/null; then
  warn "version hardcoded in source — read it from Bundle.main"; else ok "version not hardcoded"; fi

# Bundle ID binds to the store record forever, so it is checked BEFORE handoff.
BID=$(grep -m1 "PRODUCT_BUNDLE_IDENTIFIER" "$SRC"/*.xcodeproj/project.pbxproj 2>/dev/null | sed 's/.*= *//;s/;//;s/"//g')
BID_N=$(grep -c "PRODUCT_BUNDLE_IDENTIFIER" "$SRC"/*.xcodeproj/project.pbxproj 2>/dev/null)
if [ -z "$BID" ]; then
  bad "PRODUCT_BUNDLE_IDENTIFIER not found"
else
  BID_HEAD="${BID%%.*}"; BID_TAIL="${BID#*.}"
  if [ "$BID_HEAD" = "${BID_TAIL%%.*}" ] && [ "$BID" = "$BID_HEAD.$BID_HEAD" ]; then
    bad "bundle ID = $BID — Xcode default Name.Name; set com.<appname>.app"
  elif printf '%s' "$BID" | grep -qi "^com\.yourcompany"; then
    bad "bundle ID = $BID — com.yourcompany placeholder is blocked by the store"
  elif printf '%s' "$BID" | grep -qvE '^[A-Za-z][A-Za-z0-9-]*(\.[A-Za-z][A-Za-z0-9-]*)+$'; then
    bad "bundle ID = $BID — invalid format"
  elif [ "$(printf '%s' "$BID" | tr -cd '.' | wc -c | tr -d ' ')" -lt 2 ]; then
    warn "bundle ID = $BID — fewer than three segments"
  else
    ok "bundle ID = $BID"
  fi
  [ "${BID_N:-0}" -lt 2 ] && warn "PRODUCT_BUNDLE_IDENTIFIER appears $BID_N time(s) — check Debug and Release"
fi

say "3. Hidden features — network, SDKs, permissions, regional branching"
NET='URLSession|WKWebView|SFSafariViewController|URL\(string: *"http|import Firebase|import StoreKit|import AppsFlyer|import OneSignal|import Adjust|import Amplitude'
if grep -rqnE "$NET" --include="*.swift" "$APP" 2>/dev/null; then
  bad "network code / SDK / IAP found"; grep -rnE "$NET" --include="*.swift" "$APP" | head -5
else ok "no network, WebView or third-party SDKs"; fi

if grep -rqniE "Locale\.current|TimeZone\(|#if RELEASE" --include="*.swift" "$APP" 2>/dev/null; then
  bad "behaviour may depend on region/build configuration"; else ok "behaviour identical in every region"; fi

if grep -qE "INFOPLIST_KEY_NS[A-Za-z]*UsageDescription" "$SRC"/*.xcodeproj/project.pbxproj 2>/dev/null; then
  bad "permissions declared — remove unused ones"; else ok "no permissions requested"; fi

say "4. Uniqueness — fingerprint against every previously built app"
if [ -f "$APP/Shared/Glyphs.swift" ]; then
  n=$(grep -cE "^\s+case [a-z]" "$APP/Shared/Glyphs.swift" 2>/dev/null)
  ok "custom glyph set: $n symbols"
else bad "no Shared/Glyphs.swift — the app lives on stock SF Symbols"; fi
[ -f "$APP/Shared/CoverArt.swift" ] && ok "custom cover art present" || warn "no Shared/CoverArt.swift"

PC="${PIPELINE_ROOT:-$HOME/pipeline}/gates/printcheck.py"
if [ -f "$PC" ]; then
  pc_out=$(python3 "$PC" check "$SRC" 2>&1); pc_rc=$?
  printf '%s\n' "$pc_out" | grep -vE "^  printcheck:" | sed 's/^/  /'
  pc_f=$(printf '%s\n' "$pc_out" | grep -c "^  FAIL")
  pc_w=$(printf '%s\n' "$pc_out" | grep -c "^  warn")
  fails=$((fails+pc_f)); warns=$((warns+pc_w))
  [ "$pc_rc" -eq 0 ] && ok "printcheck: fingerprint diverges from the index" || bad "printcheck: fingerprint collides with previously built apps (see above)"
else
  warn "printcheck.py not found — fingerprint not compared"
fi

say "5. Layout — horizontal overflow"
# A bare ScrollView whose child is wider than the viewport becomes draggable sideways.
# Only a BARE `ScrollView(` counts: a letter to its left means a project's own clamp container.
stray=""
for f in $(grep -rlE "(^|[^A-Za-z_])ScrollView\(" --include="*.swift" "$APP" 2>/dev/null); do
  raw=$(grep -nE "(^|[^A-Za-z_])ScrollView[^A-Za-z_]" "$f" | grep -v "\.horizontal" | wc -l | tr -d ' ')
  [ "$raw" = "0" ] && continue
  grep -q "frame(width: geo.size.width" "$f" && continue     # manual clamp next to ScrollViewReader is fine
  stray="$stray $f"
done
if [ -n "$stray" ]; then
  warn "unclamped ScrollView (needs the project's clamp container or a manual clamp):"
  for f in $stray; do printf '        %s\n' "$f"; done
else ok "all vertical scrolls are clamped"; fi

say "6. Art performance"
if grep -rqnE '\.blur\(|blendMode\(|repeatForever' --include="*.swift" "$APP/Shared" 2>/dev/null; then
  bad "blur/blendMode/repeatForever in shared art — will lag"
  grep -rnE '\.blur\(|blendMode\(|repeatForever' --include="*.swift" "$APP/Shared" | head -5
else ok "no expensive operators in shared art"; fi

# A background rasterised with .drawingGroup() and reused on a SHEET tears when a second sheet
# opens on top: the cached texture is transformed, not redrawn. The check finds background types
# that call .drawingGroup() and any sheet-presented view that applies them.
bgnames=$(awk '/^ *(private )?struct [A-Za-z]+ *:/ {name=""} \
               /^ *(private )?struct [A-Za-z]+(Ground|Background) *:/ {name=$0; sub(/.*struct /,"",name); sub(/ *:.*/,"",name)} \
               /\.drawingGroup\(\)/ {if (name!="") {print name; name=""}}' \
          $(grep -rl '' --include="*.swift" "$APP/Shared" 2>/dev/null) 2>/dev/null | sort -u)
if [ -n "$bgnames" ]; then
  sheettypes=$(grep -rhA3 -E '\.(sheet|fullScreenCover)\(' --include="*.swift" "$APP" 2>/dev/null \
               | grep -oE '\b[A-Z][A-Za-z0-9]*\(' | tr -d '(' | sort -u | grep -vE '^(Binding|Text|Image|Color|Button|VStack|HStack|ZStack)$')
  sheetbg=""
  for t in $sheettypes; do
    src=$(grep -rlE "^ *(private )?struct $t *:" --include="*.swift" "$APP" 2>/dev/null | head -1)
    [ -z "$src" ] && continue
    for n in $bgnames; do
      if awk -v t="$t" -v bg="$n" '
            $0 ~ "^ *(private )?struct " t " *:" {inb=1; next}
            inb && /^ *(private )?struct [A-Za-z]+ *:/ {inb=0}
            inb && $0 ~ "\\.background\\( *" bg "\\(\\)" {found=1}
            END {exit !found}' "$src" 2>/dev/null; then
        sheetbg="$sheetbg $src:$t"
      fi
    done
  done
  if [ -n "$sheetbg" ]; then
    bad "drawingGroup background applied on a sheet view — the lower sheet's background tears under a second sheet; use a separate sheet background:"
    for f in $sheetbg; do printf '        %s\n' "$f"; done
  else ok "sheet backgrounds separated from the full-screen one"; fi
else ok "no flat background with drawingGroup found"; fi

say "7. Orientation"
if grep -q "UIInterfaceOrientationLandscape" "$SRC"/*.xcodeproj/project.pbxproj 2>/dev/null; then
  warn "landscape declared — the app is designed for portrait"; else ok "portrait only"; fi

say "8. Accessibility"
labels=$(grep -rc "accessibilityLabel" --include="*.swift" "$APP" 2>/dev/null | awk -F: '{s+=$2} END {print s+0}')
[ "$labels" -ge 20 ] && ok "accessibilityLabel: $labels" || warn "few accessibilityLabel ($labels) — icon buttons are not voiced"
fixed=$(grep -rn "font(.system(size:" --include="*.swift" "$APP" 2>/dev/null | wc -l | tr -d ' ')
if [ "$fixed" -gt 20 ]; then
  warn "$fixed fixed font sizes — text does not scale with Dynamic Type"
else ok "fonts go through the type scale (fixed: $fixed)"; fi

say "9. Root view preview"
# The root view is whatever the @main file puts into WindowGroup; its name is read, not guessed.
APPFILE=$(grep -rl "@main" --include="*.swift" "$APP" 2>/dev/null | head -1)
ROOT=$(grep -A3 "WindowGroup" "$APPFILE" 2>/dev/null | grep -oE "[A-Z][A-Za-z0-9_]*\(\)" | head -1 | sed 's/()//')
if [ -z "$ROOT" ]; then
  warn "could not determine the root view from the @main file"
else
  ROOTFILE=$(grep -rl "struct $ROOT\b" --include="*.swift" "$APP" 2>/dev/null | head -1)
  if [ -z "$ROOTFILE" ]; then warn "root view $ROOT not found in sources"
  elif grep -q "#Preview" "$ROOTFILE" 2>/dev/null; then ok "#Preview on root view ($ROOT)"
  else bad "no #Preview in $ROOTFILE — add: #Preview { $ROOT() }"; fi
fi

say "10. Delivery artifacts"
[ -f REQUIREMENTS.md ] && ok "REQUIREMENTS.md" || bad "no REQUIREMENTS.md (the spec must survive session cleanup)"
if [ ! -f APPLE_REVIEW_RESPONSE.txt ]; then
  bad "no APPLE_REVIEW_RESPONSE.txt"
else
  chars=$(wc -m < APPLE_REVIEW_RESPONSE.txt | tr -d ' ')
  if [ "$chars" -le 3500 ]; then ok "APPLE_REVIEW_RESPONSE.txt ($chars chars, fits one message)"
  elif [ "$chars" -le 4096 ]; then warn "APPLE_REVIEW_RESPONSE.txt — $chars chars, above the 3500 working ceiling"
  else bad "APPLE_REVIEW_RESPONSE.txt — $chars chars, does not fit one message (4096)"; fi
  APPNAME=$(basename "$APP")
  grep -qi "$APPNAME" APPLE_REVIEW_RESPONSE.txt 2>/dev/null && bad "review reply names the app ($APPNAME) — use 'The app'" || ok "review reply does not name the app"
  grep -qE '\*\*|```|^[0-9]+\.|^[-•]' APPLE_REVIEW_RESPONSE.txt 2>/dev/null && bad "review reply contains markdown/bullets — plain text required" || ok "review reply is plain text"
fi
if [ -f APP_STORE_METADATA.md ]; then
  ok "APP_STORE_METADATA.md"
  grep -qiE "^#+ .*(review(er)? note|notes for review)" APP_STORE_METADATA.md && ok "reviewer note section present" || bad "no «Reviewer note» section — every feature must be described with specificity"
  grep -qiE "support url" APP_STORE_METADATA.md && ok "Support URL mentioned" || warn "no Support URL line"
  grep -qiE "^#+ .*(build facts|build date)" APP_STORE_METADATA.md && ok "build facts section present" || warn "no «Build facts» section (bundle ID, build date)"
else warn "no APP_STORE_METADATA.md"; fi

# Saturated categories where stores reject new submissions without a meaningfully different experience.
if [ -f REQUIREMENTS.md ] && grep -qiE "dating|flashlight|wallpaper|fortune|horoscope|timer|sound effect|drinking|знакомств|фонарик|обои|гадани|гороскоп|таймер" REQUIREMENTS.md; then
  warn "spec touches a saturated category (dating/flashlight/wallpaper/timer/fortune/sound effects/drinking) — needs a domain mechanic generic apps lack"
else ok "spec outside saturated categories"; fi

printf '\n\033[1mTOTAL:\033[0m %d FAIL, %d warn\n' "$fails" "$warns"
[ "$fails" -gt 0 ] && exit 1
exit 0
