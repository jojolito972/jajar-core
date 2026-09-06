"""
automation/serveur_appel_vocal.py — Serveur d'Appel Vocal Téléphonique Ultra-Robuste
Flux binaire brut direct (Zéro corruption multipart), Double Mode VAD + Push-to-Talk, Diagnostic Live.
"""

from __future__ import annotations

import asyncio
import datetime
import io
import json
import logging
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from core.llm_router import router
from google.genai import types

logger: Final[logging.Logger] = logging.getLogger("jajar.phone_server")

HTML_PHONE_INTERFACE: Final[str] = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Atelier Laura Puntillo & JAJAR</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: #0a0c10; color: #fff; height: 100vh; display: flex; flex-direction: column; justify-content: space-between; align-items: center; padding: 25px 20px 20px; text-align: center; overflow: hidden; }
        .header { margin-top: 5px; }
        .avatar { width: 85px; height: 85px; border-radius: 50%; background: linear-gradient(135deg, #10b981, #059669); margin: 0 auto 10px; display: flex; align-items: center; justify-content: center; font-size: 38px; box-shadow: 0 0 25px rgba(16, 185, 129, 0.4); border: 2px solid rgba(255,255,255,0.2); }
        .title { font-size: 20px; font-weight: 700; }
        .status-badge { display: inline-block; margin-top: 6px; padding: 5px 14px; background: rgba(16, 185, 129, 0.15); color: #34d399; border-radius: 20px; font-size: 13px; font-weight: 600; border: 1px solid rgba(52, 211, 153, 0.3); }
        .timer { font-size: 13px; color: #94a3b8; margin-top: 4px; font-family: monospace; }
        
        .wave-container { width: 100%; max-width: 300px; height: 50px; display: flex; align-items: center; justify-content: center; gap: 4px; }
        .bar { width: 4px; height: 6px; background: #34d399; border-radius: 2px; transition: height 0.08s ease; }
        
        .dialogue-card { width: 100%; max-width: 340px; height: 130px; background: rgba(255,255,255,0.03); border-radius: 16px; padding: 12px 14px; font-size: 13px; line-height: 1.45; color: #e2e8f0; overflow-y: auto; border: 1px solid rgba(255,255,255,0.06); text-align: left; }
        
        /* Bouton Push-To-Talk & Contrôles */
        .push-talk-btn { width: 100%; max-width: 320px; padding: 16px; background: #10b981; color: #fff; border: none; border-radius: 16px; font-size: 16px; font-weight: 700; cursor: pointer; box-shadow: 0 0 20px rgba(16, 185, 129, 0.4); user-select: none; -webkit-user-select: none; }
        .push-talk-btn:active, .push-talk-btn.recording { background: #ef4444 !important; box-shadow: 0 0 25px rgba(239, 68, 68, 0.6) !important; }
        
        .controls { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; width: 100%; max-width: 320px; margin-top: 10px; }
        .btn-circle { width: 56px; height: 56px; border-radius: 50%; background: rgba(255,255,255,0.1); border: none; color: #fff; font-size: 18px; display: flex; align-items: center; justify-content: center; margin: 0 auto; cursor: pointer; }
        .btn-end { background: #ef4444 !important; }
        .btn-label { font-size: 11px; color: #94a3b8; margin-top: 4px; }

        #startModal { position: fixed; inset: 0; background: #0a0c10; display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 100; padding: 30px; }
        .btn-start { padding: 16px 36px; font-size: 18px; font-weight: 700; background: #10b981; color: #fff; border: none; border-radius: 30px; cursor: pointer; box-shadow: 0 0 30px rgba(16, 185, 129, 0.5); margin-top: 25px; }
    </style>
</head>
<body>
    <div id="startModal">
        <div style="font-size: 50px; margin-bottom: 15px;">👢</div>
        <h2 style="font-size: 22px; font-weight: 700; margin-bottom: 8px;">Atelier Laura Puntillo & JAJAR</h2>
        <p style="font-size: 14px; color: #94a3b8; max-width: 280px; line-height: 1.4;">Appel vocal en direct. Appuie pour démarrer la liaison audio.</p>
        <button class="btn-start" onclick="demarrerAppel()">📞 Démarrer l'Appel</button>
    </div>

    <div class="header">
        <div class="avatar" id="avatarIcon">👢</div>
        <div class="title" id="agentTitle">ALBA — ATELIER BESPOKE</div>
        <div class="status-badge" id="statusBadge">🟢 En attente de parole...</div>
        <div class="timer" id="callTimer">00:00</div>
    </div>

    <div class="wave-container" id="wave"></div>

    <div class="dialogue-card" id="dialogue">
        <span style="color:#94a3b8;">« Tu peux parler librement (détection auto) OU maintenir le gros bouton vert ci-dessous pour dicter... »</span>
    </div>

    <div style="width: 100%; max-width: 320px;">
        <button class="push-talk-btn" id="btnPushTalk" 
                onmousedown="startPushRecording()" onmouseup="stopPushRecording()"
                ontouchstart="startPushRecording(event)" ontouchend="stopPushRecording(event)">
            🎙️ MAINTENIR POUR PARLER
        </button>

        <div class="controls">
            <div><button class="btn-circle" id="btnAutoVad" onclick="toggleAutoVAD()">⚡</button><div class="btn-label" id="lblAutoVad">Auto: ON</div></div>
            <div><button class="btn-circle btn-end" onclick="quitterAppel()">📞</button><div class="btn-label">Quitter</div></div>
            <div><button class="btn-circle" onclick="switchAgent()">🔄</button><div class="btn-label">Agent</div></div>
        </div>
    </div>

    <script>
        let audioContext, analyser, streamActive, mediaRecorder;
        let audioChunks = [];
        let isSpeaking = false, silenceTimer = null, isProcessing = false;
        let activeAgent = "alba";
        let autoVAD = true;
        let seconds = 0;
        let isManualPush = false;
        let supportedMime = "audio/webm";

        const waveBox = document.getElementById('wave');
        for (let i = 0; i < 28; i++) {
            let b = document.createElement('div');
            b.className = 'bar';
            waveBox.appendChild(b);
        }
        const bars = document.querySelectorAll('.bar');

        setInterval(() => {
            if (streamActive) {
                seconds++;
                let m = String(Math.floor(seconds / 60)).padStart(2, '0');
                let s = String(seconds % 60).padStart(2, '0');
                document.getElementById('callTimer').innerText = `${m}:${s}`;
            }
        }, 1000);

        async function demarrerAppel() {
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                await audioContext.resume();

                streamActive = await navigator.mediaDevices.getUserMedia({ 
                    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } 
                });
                
                analyser = audioContext.createAnalyser();
                analyser.fftSize = 64;
                let source = audioContext.createMediaStreamSource(streamActive);
                source.connect(analyser);

                if (MediaRecorder.isTypeSupported('audio/webm; codecs=opus')) {
                    supportedMime = 'audio/webm; codecs=opus';
                } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
                    supportedMime = 'audio/mp4';
                } else {
                    supportedMime = '';
                }

                document.getElementById('startModal').style.display = 'none';
                initRecorderLoop();
                lancerVADLoop();
            } catch (err) {
                alert("Erreur accès micro : " + err.message);
            }
        }

        function initRecorderLoop() {
            audioChunks = [];
            try {
                mediaRecorder = supportedMime ? new MediaRecorder(streamActive, { mimeType: supportedMime }) : new MediaRecorder(streamActive);
            } catch (e) {
                mediaRecorder = new MediaRecorder(streamActive);
            }
            mediaRecorder.ondataavailable = e => { if (e.data && e.data.size > 0) audioChunks.push(e.data); };
            mediaRecorder.start(100);
        }

        function lancerVADLoop() {
            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);

            function inspecter() {
                if (isProcessing) {
                    requestAnimationFrame(inspecter);
                    return;
                }
                analyser.getByteFrequencyData(dataArray);
                let sum = 0;
                for (let i = 0; i < bufferLength; i++) {
                    sum += dataArray[i];
                    if (bars[i]) bars[i].style.height = Math.max(6, (dataArray[i] / 255) * 45) + 'px';
                }
                let avg = sum / bufferLength;

                if (autoVAD && !isManualPush) {
                    if (avg > 28) {
                        if (!isSpeaking) {
                            isSpeaking = true;
                            document.getElementById('statusBadge').innerText = "🗣️ Écoute de votre voix...";
                            document.getElementById('statusBadge').style.color = "#60a5fa";
                            clearTimeout(silenceTimer);
                        }
                    } else if (isSpeaking) {
                        if (!silenceTimer) {
                            silenceTimer = setTimeout(() => {
                                isSpeaking = false;
                                silenceTimer = null;
                                declencherEnvoi();
                            }, 850);
                        }
                    }
                }
                requestAnimationFrame(inspecter);
            }
            inspecter();
        }

        function startPushRecording(e) {
            if (e) e.preventDefault();
            if (isProcessing) return;
            isManualPush = true;
            isSpeaking = true;
            document.getElementById('btnPushTalk').classList.add('recording');
            document.getElementById('btnPushTalk').innerText = "🔴 ENREGISTREMENT EN COURS...";
            document.getElementById('statusBadge').innerText = "🗣️ Enregistrement manuel...";
        }

        function stopPushRecording(e) {
            if (e) e.preventDefault();
            if (!isManualPush) return;
            isManualPush = false;
            isSpeaking = false;
            document.getElementById('btnPushTalk').classList.remove('recording');
            document.getElementById('btnPushTalk').innerText = "🎙️ MAINTENIR POUR PARLER";
            declencherEnvoi();
        }

        function declencherEnvoi() {
            if (isProcessing || !mediaRecorder || mediaRecorder.state === "inactive") return;
            isProcessing = true;
            document.getElementById('statusBadge').innerText = "⏳ Envoi & Réflexion...";
            document.getElementById('statusBadge').style.color = "#f59e0b";

            mediaRecorder.stop();
            mediaRecorder.onstop = async () => {
                const blobType = supportedMime.split(';')[0] || 'audio/webm';
                const audioBlob = new Blob(audioChunks, { type: blobType });
                audioChunks = [];

                if (audioBlob.size > 800) {
                    try {
                        let resp = await fetch('/api/call/process?agent=' + activeAgent, {
                            method: 'POST',
                            headers: { 'Content-Type': blobType },
                            body: audioBlob
                        });
                        let data = await resp.json();

                        if (data.status === "ok") {
                            document.getElementById('dialogue').innerHTML = `<b>Vous :</b> ${data.user_text}<br><br><b style="color:#34d399;">${activeAgent.toUpperCase()} :</b> ${data.answer}`;
                            document.getElementById('statusBadge').innerText = `🔊 ${activeAgent.toUpperCase()} parle...`;
                            document.getElementById('statusBadge').style.color = "#34d399";

                            let audio = new Audio('/api/call/audio_reply?' + Date.now());
                            audio.onended = () => {
                                isProcessing = false;
                                document.getElementById('statusBadge').innerText = "🟢 En attente de parole...";
                                document.getElementById('statusBadge').style.color = "#34d399";
                                initRecorderLoop();
                            };
                            audio.onerror = () => {
                                isProcessing = false;
                                initRecorderLoop();
                            };
                            await audio.play();
                        } else {
                            document.getElementById('dialogue').innerHTML = `<span style="color:#f87171;">⚠️ ${data.message || 'Non compris'}</span>`;
                            isProcessing = false;
                            initRecorderLoop();
                        }
                    } catch (err) {
                        document.getElementById('dialogue').innerHTML = `<span style="color:#f87171;">⚠️ Erreur réseau : ${err.message}</span>`;
                        isProcessing = false;
                        initRecorderLoop();
                    }
                } else {
                    isProcessing = false;
                    document.getElementById('statusBadge').innerText = "🟢 En attente de parole...";
                    initRecorderLoop();
                }
            };
        }

        function toggleAutoVAD() {
            autoVAD = !autoVAD;
            document.getElementById('lblAutoVad').innerText = autoVAD ? "Auto: ON" : "Auto: OFF";
            document.getElementById('btnAutoVad').style.background = autoVAD ? "rgba(255,255,255,0.1)" : "#f59e0b";
        }

        function switchAgent() {
            activeAgent = activeAgent === "alba" ? "jarvis" : "alba";
            document.getElementById('agentTitle').innerText = activeAgent === "alba" ? "ALBA — ATELIER BESPOKE" : "JAJAR — STUDIO SUPERVISEUR";
            document.getElementById('avatarIcon').innerText = activeAgent === "alba" ? "👢" : "🤖";
        }

        function quitterAppel() {
            if (streamActive) streamActive.getTracks().forEach(t => t.stop());
            window.location.href = "about:blank";
        }
    </script>
</body>
</html>
"""


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


class PhoneCallHTTPHandler(BaseHTTPRequestHandler):
    dernier_audio_reponse: bytes = b""

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path in ("/", "/call", "/phone", "/call/", "/phone/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(HTML_PHONE_INTERFACE.encode("utf-8"))
            return

        if self.path.startswith("/api/call/audio_reply"):
            if self.dernier_audio_reponse:
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(self.dernier_audio_reponse)
                return
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        if self.path.startswith("/api/call/process"):
            length = int(self.headers.get("Content-Length", 0))
            audio_bytes = self.rfile.read(length)
            content_type = self.headers.get("Content-Type", "audio/webm").split(";")[0].strip()

            parsed_url = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed_url.query)
            agent_cible = params.get("agent", ["alba"])[0]

            print(f"\n[APPEL] 🎙️ Audio brut reçu ({len(audio_bytes)} octets, format: {content_type})")

            # 1. Transcription Multimodale Gemini Directe
            client = config.GENAI_CLIENT
            prompt_oral = (
                "Tu es au téléphone en direct avec Den ou Laura.\n"
                "Transcris fidèlement ce message vocal.\n"
                "Format JSON strict : {\"texte\": \"...\", \"langue\": \"fr\" | \"it\"}"
            )

            candidats = router._obtenir_modeles_gemini_valides()
            candidats = [m for m in candidats if "flash" in m or "pro" in m]
            if not candidats:
                candidats = [config.MODELE_TEXTE_GEMINI, "gemini-2.5-flash", "gemini-2.0-flash"]

            user_text = ""
            langue = "fr"

            for mod in candidats:
                try:
                    res_trans = client.models.generate_content(
                        model=mod,
                        contents=[types.Part.from_bytes(data=audio_bytes, mime_type=content_type), prompt_oral],
                        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
                    )
                    if res_trans.text:
                        data_t = json.loads(res_trans.text.strip())
                        user_text = data_t.get("texte", "").strip()
                        langue = data_t.get("langue", "fr")
                        if user_text:
                            break
                except Exception as e:
                    logger.warning(f"Échec transcription ({mod}) : {e}")
                    continue

            if not user_text:
                print("  ⚠️ [APPEL] Transcription vide.")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b'{"status":"error","message":"Audio non compris, r\xc3\xa9p\xc3\xa8te s\'il te pla\xc3\xaet."}')
                return

            print(f"  🗣️ [VOIX] Reçu ({langue.upper()}) : « {user_text} »")

            # 2. Inférence Orale Directe
            prompt_rep = (
                f"Tu es {agent_cible.upper()} en direct au téléphone avec {'Laura' if agent_cible == 'alba' else 'Den'}.\n"
                f"Langue : {'Italien' if langue == 'it' else 'Français'}.\n\n"
                "RÈGLE D'OR ORALE :\n"
                "Réponds en 1 ou 2 phrases concises, chaleureuses et rythmées, SANS AUCUN caractère markdown."
            )

            try:
                res_llm = client.models.generate_content(
                    model=config.MODELE_TEXTE_GEMINI,
                    contents=f"{prompt_rep}\n\nInterlocuteur : '{user_text}'",
                    config=types.GenerateContentConfig(temperature=0.3),
                )
                reponse_orale = re.sub(r"[*#`_\[\]>]", "", res_llm.text.strip()) if res_llm.text else "Bien reçu."
            except Exception as e:
                reponse_orale = "C'est bien noté, je m'en occupe."

            print(f"  🤖 [{agent_cible.upper()}] Réponse : « {reponse_orale} »")

            # 3. Synthèse Vocale Téléphonique (Edge-TTS)
            try:
                import edge_tts
                voice_id = "it-IT-ElsaNeural" if (agent_cible == "alba" and langue == "it") else "fr-FR-VivienneNeural"
                audio_out = config.AUDIO_DIR / f"phone_reply_{os.urandom(4).hex()}.mp3"

                async def _tts():
                    comm = edge_tts.Communicate(reponse_orale, voice_id)
                    await comm.save(str(audio_out))

                asyncio.run(_tts())
                PhoneCallHTTPHandler.dernier_audio_reponse = audio_out.read_bytes()
                if audio_out.exists():
                    audio_out.unlink()
                print(f"  🔊 [TTS] Synthèse audio envoyée ({len(PhoneCallHTTPHandler.dernier_audio_reponse)} octets).")
            except Exception as e:
                logger.error(f"Échec TTS : {e}")

            # Réponse JSON au navigateur
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            payload = json.dumps({"status": "ok", "user_text": user_text, "answer": reponse_orale}, ensure_ascii=False)
            self.wfile.write(payload.encode("utf-8"))


def main() -> None:
    server_address = ("0.0.0.0", 8765)
    httpd = ReusableHTTPServer(server_address, PhoneCallHTTPHandler)
    print("📞 Serveur d'Appel Vocal Haute Précision Prêt sur le port 8765.")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
