"""
Attribution deterministe d'une voix par avion - Application d'entrainement ATC
==============================================================================
Chaque indicatif (callsign) recoit une voix STABLE tiree d'un pool configurable
(env ATC_TTS_VOICES, liste separee par des virgules) : hachage crc32 -> index.
crc32 est stable inter-plateformes et inter-sessions : le meme avion garde la
meme voix pendant toute la session (et d'une session a l'autre a pool constant).
Un pool plus petit que le nombre d'avions produit des doublons (assume).
"""
import zlib


def parse_pool(raw):
    """Chaine "a, b,,c" -> ["a", "b", "c"] (espaces et entrees vides ignores)."""
    if not raw:
        return []
    return [v.strip() for v in str(raw).split(",") if v.strip()]


def voice_for_callsign(callsign, pool):
    """Voix deterministe du pool pour un indicatif (None si pool vide).

    Insensible a la casse et aux espaces peripheriques : 'afr1234' et
    'AFR1234 ' donnent la meme voix."""
    if not pool:
        return None
    key = str(callsign or "").strip().upper().encode("utf-8")
    return pool[zlib.crc32(key) % len(pool)]
