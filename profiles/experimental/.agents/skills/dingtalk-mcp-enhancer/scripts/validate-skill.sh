#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_root="$(cd "${script_dir}/.." && pwd)"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_file() {
  [[ -f "$1" ]] || fail "missing required file"
}

require_text() {
  local pattern="$1"
  local file="$2"
  rg -q -- "$pattern" "$file" || fail "required content is missing"
}

skill_file="${skill_root}/SKILL.md"
agent_file="${skill_root}/agents/openai.yaml"
capabilities="${skill_root}/references/capabilities.md"
validation="${skill_root}/references/validation.md"
diagnostics="${skill_root}/references/diagnostics.md"
axls="${skill_root}/references/axls.md"
able="${skill_root}/references/able.md"
cases="${skill_root}/references/cases.md"
image_fixture="${skill_root}/assets/validation/dingtalk-validation-image.png"
attachment_fixture="${skill_root}/assets/validation/dingtalk-validation-attachment.txt"
import_fixture="${skill_root}/assets/validation/dingtalk-validation-import.csv"

for required in \
  "$skill_file" "$agent_file" \
  "${skill_root}/references/routing.md" \
  "${skill_root}/references/availability.md" \
  "${skill_root}/references/operations.md" \
  "${skill_root}/references/diagnostics.md" \
  "${skill_root}/references/adoc.md" \
  "${skill_root}/references/axls.md" \
  "${skill_root}/references/able.md" \
  "$capabilities" "$validation" \
  "${skill_root}/references/cases.md" \
  "${script_dir}/check_links.py" \
  "$image_fixture" "$attachment_fixture" "$import_fixture"; do
  require_file "$required"
done

require_text '^name: dingtalk-mcp-enhancer$' "$skill_file"
require_text '^description: .+' "$skill_file"
require_text '钉钉空间中的普通文件' "$skill_file"
require_text 'create_chart.*create_charts' "$skill_file"
require_text 'mode: read | write | mixed' "${skill_root}/references/operations.md"
require_text 'recommended' "$capabilities"
require_text 'not-yet-tested' "$capabilities"
require_text 'observed-issue' "$capabilities"
require_text 'unavailable' "$capabilities"
require_text 'TOOL_MISSING' "${skill_root}/references/availability.md"
require_text 'TOOL_NOT_HOT_LOADED' "${skill_root}/references/availability.md"
require_text 'ROUTE_TOOL_MISSING' "${skill_root}/references/availability.md"
require_text 'CREATE_TOOL_MISSING' "${skill_root}/references/availability.md"
require_text 'AUTH_FAILED' "${skill_root}/references/availability.md"
require_text 'SAFE_TRANSFER_CHANNEL_UNAVAILABLE' "$diagnostics"
require_text 'CONFIRMATION_REQUIRED' "$diagnostics"
require_text 'ACCESS_STATE_UNVERIFIED' "$diagnostics"
require_text 'RESOURCE_STATE_INCONSISTENT' "$diagnostics"
require_text 'structuredContent.success' "$axls"
require_text 'update_filter' "$axls"
require_text 'get_chart_share' "$able"
require_text 'Chart 创建后隐式分享' "$cases"
require_text '空 Dashboard 混入外来 Chart' "$cases"
require_text 'Agent-DingTalk-MCP-Validation-YYYYMMDD-HHMMSS-\*' "$validation"
require_text 'allow_implicit_invocation: true' "$agent_file"

[[ "$(rg -c '^mcp__dingtalk__' "$capabilities")" == "40" ]] || fail "dated document tool snapshot is incomplete"
[[ "$(rg -c '^mcp__dingtalk_sheet__' "$capabilities")" == "74" ]] || fail "dated sheet tool snapshot is incomplete"
[[ "$(rg -c '^mcp__dingtalk_ai_table__' "$capabilities")" == "56" ]] || fail "dated AI-table tool snapshot is incomplete"

check_fixture() {
  local path="$1"
  local expected_size="$2"
  local expected_sha="$3"
  local actual_size actual_sha
  actual_size="$(wc -c < "$path" | tr -d ' ')"
  actual_sha="$(shasum -a 256 "$path" | awk '{print $1}')"
  [[ "$actual_size" == "$expected_size" ]] || fail "validation fixture size mismatch"
  [[ "$actual_sha" == "$expected_sha" ]] || fail "validation fixture sha256 mismatch"
}

check_fixture "$image_fixture" 830600 388782231ef66f9ab044e673d95cea358f58d9779152097235fb5140e44b35e3
check_fixture "$attachment_fixture" 289 2958d7fbb95d7699b250f32799db8f061ddd63eaf934d0405f665f2684fc34c9
check_fixture "$import_fixture" 99 20b4d59e3b409d39c05e51e478e4195b5ff92918824ca0ea62f6dce35c680028
file "$image_fixture" | rg -q 'PNG image data' || fail "image fixture type mismatch"
file "$attachment_fixture" | rg -q 'text' || fail "attachment fixture type mismatch"
file "$import_fixture" | rg -q 'CSV text' || fail "import fixture type mismatch"

authorization_key='author''ization'
cookie_key='coo''kie'
access_key='access''key'
signature_key='signa''ture'
security_token_key='x-oss-security-''token'
secret_pattern="(${authorization_key}:[[:space:]]*(bearer|basic)[[:space:]]+[^ <]+|${cookie_key}:[[:space:]]*[^ <]+|${access_key}(id)?=[^& <]+|${signature_key}=[^& <]+|${security_token_key}:[[:space:]]*[^ <]+|[?&]key=[^& <]+)"
while IFS= read -r -d '' candidate; do
  if rg -q -i -- "$secret_pattern" "$candidate"; then
    fail "possible credential or signed request found in a text asset"
  fi
done < <(find "$skill_root" -type f \( \
  -name '*.md' -o -name '*.yaml' -o -name '*.yml' -o -name '*.sh' -o \
  -name '*.py' -o -name '*.json' -o -name '*.csv' -o -name '*.txt' -o \
  -name '*.ps1' \) -print0)

if find "$skill_root" -type f \( -name '*.bak' -o -name '*~' -o -name '.DS_Store' \) | rg -q .; then
  fail "backup or metadata files found"
fi

skill_lines="$(wc -l < "$skill_file" | tr -d ' ')"
(( skill_lines <= 500 )) || fail "SKILL.md exceeds 500 lines"

python3 "${script_dir}/check_links.py"
echo "DingTalk MCP enhancer validation passed"
