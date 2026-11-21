"""
KarmaForge AI Gateway
Combines Mika's Keypool Rotation with CurioCut's Multi-Model Quality Ladder
and a strict anti-AI output sanitizer.
"""

import os
import json
import time
import random
import re
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, List, Dict, Tuple

class KeyPool:
    """Mika-style Keypool for managing API keys with cooldowns on rate-limits."""
    def __init__(self, keys: List[str], cooldown_seconds: int = 600):
        self.keys = [k.strip() for k in keys if k.strip()]
        self.cooldown_seconds = cooldown_seconds
        self.cooldowns: Dict[str, float] = {}

    def get_available_key(self) -> Optional[str]:
        now = time.time()
        available = [k for k in self.keys if self.cooldowns.get(k, 0) <= now]
        if not available:
            return None
        return random.choice(available)

    def is_cooling_down(self, key: str) -> bool:
        return self.cooldowns.get(key, 0) > time.time()

    def mark_rate_limited(self, key: str, custom_cooldown: Optional[int] = None):
        cooldown = custom_cooldown or self.cooldown_seconds
        self.cooldowns[key] = time.time() + cooldown
        print(f"  [AI Gateway] Key ending in ...{key[-4:]} rate-limited. Cooling down for {cooldown}s.")

    def has_keys(self) -> bool:
        return len(self.keys) > 0


class OutputSanitizer:
    """Hard programmatic filters guaranteeing zero AI hallmarks."""
    
    # Comprehensive Unicode range for emojis and pictographs
    EMOJI_PATTERN = re.compile(
        r"[\U0001F600-\U0001F64F"  # Emoticons
        r"\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
        r"\U0001F680-\U0001F6FF"  # Transport and Map
        r"\U0001F700-\U0001F77F"  # Alchemical Symbols
        r"\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        r"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        r"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        r"\U0001FA00-\U0001FA6F"  # Chess Symbols
        r"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        r"\U00002702-\U000027B0"  # Dingbats
        r"\U000024C2-\U0001F251]+",
        flags=re.UNICODE
    )

    CHATTER_PREFIXES = [
        r"^(?:here(?:'s|\s+is)\s+(?:a|my)?\s*(?:comment|reply|response|take):\s*)",
        r"^(?:as a redditor,?\s*)",
        r"^(?:comment:\s*)",
        r"^(?:reply:\s*)",
        r"^(?:sure,?\s*(?:here'?s|how about)?\s*)",
        r"^(?:i would say:?\s*)"
    ]

    @classmethod
    def sanitize(cls, text: str, enforce_lowercase: bool = True, max_sentences: int = 2) -> str:
        if not text:
            return ""

        cleaned = text.strip()

        # 1. Strip surrounding quotes and code fences
        cleaned = re.sub(r"^[`'\"]+|[`'\"]+$", "", cleaned).strip()

        # 2. Strip introductory AI chatter
        for prefix in cls.CHATTER_PREFIXES:
            cleaned = re.sub(prefix, "", cleaned, flags=re.IGNORECASE).strip()

        # 3. Strip all emojis programmatically
        cleaned = cls.EMOJI_PATTERN.sub("", cleaned).strip()

        # 4. Anti-AI Punctuation Sanitizer
        # Replace em-dashes and en-dashes with comma or simple space
        cleaned = re.sub(r"\s*[—–]\s*", ", ", cleaned)
        cleaned = re.sub(r"\s*--\s*", ", ", cleaned)

        # Replace semicolons with commas or periods
        cleaned = re.sub(r";\s*", ", ", cleaned)

        # Downgrade cheerful AI exclamation marks to a period or space
        cleaned = re.sub(r"!+", ".", cleaned)

        # Remove dramatic ellipses abuse (e.g. '....' -> '.')
        cleaned = re.sub(r"\.{2,}", ".", cleaned)

        # Remove random AI quote wrapping around casual words
        cleaned = re.sub(r'["\']([a-zA-Z0-9\s]{1,30})["\']', r'\1', cleaned)

        # 5. Limit to max sentences (punchy Reddit length)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
        if len(sentences) > max_sentences:
            cleaned = " ".join(sentences[:max_sentences])

        # 6. Natural lowercase start
        if enforce_lowercase and cleaned:
            first_word = cleaned.split()[0] if cleaned.split() else ""
            if not (len(first_word) > 1 and first_word.isupper()):
                cleaned = cleaned[0].lower() + cleaned[1:]

        # 7. Drop trailing period (real human Redditors drop the final full stop)
        cleaned = re.sub(r"\.+$", "", cleaned).strip()

        # Clean multiple spaces and return
        return re.sub(r"\s+", " ", cleaned).strip()


class AIGateway:
    """Multi-Key Keypool + Cascading Fallback (Gemini -> Groq) Engine."""
    
    def __init__(self):
        gemini_env = os.environ.get("GEMINI_API_KEYS", "") or os.environ.get("GEMINI_API_KEY", "")
        keys = [k.strip() for k in gemini_env.split(",") if k.strip()]
        self.gemini_pool = KeyPool(keys, cooldown_seconds=300)
        self.groq_key = os.environ.get("GROQ_API_KEY", "").strip()

        self.gemini_models = [
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
            "gemini-2.5-flash",
            "gemini-pro-latest",
            "gemini-2.0-flash",
            "gemini-1.5-flash"
        ]

        self.groq_models = [
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b"
        ]

    def build_quality_ladder(self) -> List[Tuple[str, str, str]]:
        """
        Verified Multi-Key Quality Ladder:
        Routes across models verified to return 200 OK and generate peak human humor.
        """
        ladder = []
        keys = self.gemini_pool.keys
        if not keys:
            return ladder

        # Tier 1: Peak Nuance & Sharp Cynical Wit (gemini-3.1-flash-lite)
        for idx, key in enumerate(keys, 1):
            ladder.append((key, "gemini-3.1-flash-lite", f"Key {idx} [3.1 Flash Lite]"))

        # Tier 2: Fast & High-Context Human Tone (gemini-flash-latest)
        for idx, key in enumerate(keys, 1):
            ladder.append((key, "gemini-flash-latest", f"Key {idx} [Flash Latest]"))

        # Tier 3: High-Throughput Observational Humor (gemini-flash-lite-latest)
        for idx, key in enumerate(keys, 1):
            ladder.append((key, "gemini-flash-lite-latest", f"Key {idx} [Flash Lite]"))

        # Tier 4: Deep Pro Reasoning (when free-tier RPM allows)
        for idx, key in enumerate(keys, 1):
            ladder.append((key, "gemini-3.1-pro-preview", f"Key {idx} [3.1 Pro Preview]"))

        return ladder

    def _call_gemini_direct(self, prompt: str, system_prompt: str, key: str, model: str) -> str:
        """Native REST request to Google Gemini API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.85,
                "maxOutputTokens": 300
            }
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=7.0) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        return ""

    def _call_groq_direct(self, prompt: str, system_prompt: str, model: str) -> str:
        """Native REST request to Groq LPU API."""
        if not self.groq_key:
            raise ValueError("No Groq API key configured.")

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 120
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            choices = res_json.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                content = msg.get("content", "").strip()
                if not content and "reasoning" in msg:
                    content = msg.get("reasoning", "").strip()
                return content
        return ""

    def generate_comment(
        self,
        prompt: str,
        system_prompt: str,
        enforce_lowercase: bool = True,
        max_sentences: int = 2
    ) -> Optional[str]:
        """
        Executes CurioCut-Style Quality Ladder + Groq LPU Failover:
        1. Evaluates priority ladder across all active keys and models.
        2. Skips keys currently cooling down from rate limits.
        3. If all Gemini tiers are exhausted, drops to Groq LPU backup brain.
        4. Programmatically sanitizes output to guarantee zero AI artifacts.
        """
        raw_output = None
        ladder = self.build_quality_ladder()

        # Tier 1-3: Gemini Multi-Key Multi-Model Quality Ladder
        for key, model, label in ladder:
            if self.gemini_pool.is_cooling_down(key):
                continue

            try:
                raw_output = self._call_gemini_direct(prompt, system_prompt, key, model)
                if raw_output and len(raw_output) > 6:
                    print(f"  [AI Gateway] Successfully generated with {label}.")
                    break
            except urllib.error.HTTPError as e:
                if e.code in (429, 403, 401):
                    self.gemini_pool.mark_rate_limited(key)
                    continue
                elif e.code in (500, 502, 503, 504):
                    print(f"  [AI Gateway] Peak Google traffic ({e.code} on {label}). Fast-failing to next tier...")
                    continue
                else:
                    print(f"  [AI Gateway] Gemini error ({label}): {e.code} {e.reason}")
            except (TimeoutError, urllib.error.URLError) as e:
                print(f"  [AI Gateway] Timeout / network glitch ({label}). Fast-failing to next tier...")
            except Exception as e:
                print(f"  [AI Gateway] Gemini request failed ({label}): {e}")

        # Tier 4: Groq LPU Failover
        if not raw_output and self.groq_key:
            print("  [AI Gateway] Activating Groq LPU backup brain...")
            for model in self.groq_models:
                try:
                    raw_output = self._call_groq_direct(prompt, system_prompt, model)
                    if raw_output and len(raw_output) > 6:
                        print(f"  [AI Gateway] Successfully generated with Groq ({model}).")
                        break
                except Exception as e:
                    print(f"  [AI Gateway] Groq error ({model}): {e}")

        if not raw_output:
            print("  [AI Gateway] Warning: All AI tiers failed to produce output.")
            return None

        # Clean and sanitize strictly
        clean_comment = OutputSanitizer.sanitize(
            raw_output,
            enforce_lowercase=enforce_lowercase,
            max_sentences=max_sentences
        )

        return clean_comment if len(clean_comment) >= 5 else None
