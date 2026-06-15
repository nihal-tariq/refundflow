/**
 * useVoiceSession — manages the full lifecycle of a LiveKit voice call.
 *
 * States:
 *   idle       → user has not started a call
 *   connecting → token being fetched + room being joined
 *   active     → in a live call with the agent
 *   error      → something went wrong (message exposed for the UI)
 *
 * The hook is self-contained: it tears down the room on unmount and
 * on explicit disconnect(), so the parent component is state-free.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Room,
  RoomEvent,
  Track,
  RemoteTrackPublication,
  RemoteParticipant,
  ConnectionState,
} from "livekit-client";
import { fetchVoiceToken } from "@/api/voiceApi";

export type VoiceState = "idle" | "connecting" | "active" | "error";

export interface UseVoiceSessionReturn {
  voiceState: VoiceState;
  isMuted: boolean;
  agentSpeaking: boolean;
  errorMessage: string | null;
  connect: () => Promise<void>;
  disconnect: () => void;
  toggleMute: () => void;
}

export function useVoiceSession(customerId: string): UseVoiceSessionReturn {
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [isMuted, setIsMuted] = useState(false);
  const [agentSpeaking, setAgentSpeaking] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const roomRef = useRef<Room | null>(null);
  // Keep a map of <trackSid → HTMLAudioElement> so we can remove them on leave
  const audioEls = useRef<Map<string, HTMLAudioElement>>(new Map());

  // ── cleanup ──────────────────────────────────────────────────────────────
  const cleanup = useCallback(() => {
    audioEls.current.forEach((el) => {
      el.pause();
      el.srcObject = null;
      el.remove();
    });
    audioEls.current.clear();

    if (roomRef.current) {
      roomRef.current.removeAllListeners();
      roomRef.current.disconnect();
      roomRef.current = null;
    }
  }, []);

  useEffect(() => () => cleanup(), [cleanup]);

  // ── attach a remote audio track to the DOM ───────────────────────────────
  const attachTrack = useCallback(
    (pub: RemoteTrackPublication, _participant: RemoteParticipant) => {
      if (pub.kind !== Track.Kind.Audio || !pub.track) return;
      const el = pub.track.attach();
      el.autoplay = true;
      document.body.appendChild(el);
      audioEls.current.set(pub.trackSid, el);
    },
    [],
  );

  const detachTrack = useCallback((pub: RemoteTrackPublication) => {
    const el = audioEls.current.get(pub.trackSid);
    if (el) {
      el.pause();
      el.srcObject = null;
      el.remove();
      audioEls.current.delete(pub.trackSid);
    }
  }, []);

  // ── connect ───────────────────────────────────────────────────────────────
  const connect = useCallback(async () => {
    if (voiceState !== "idle" && voiceState !== "error") return;

    setVoiceState("connecting");
    setErrorMessage(null);

    try {
      const { token, url } = await fetchVoiceToken(customerId);

      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });
      roomRef.current = room;

      // ── room event wiring ────────────────────────────────────────────────
      room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
        if (state === ConnectionState.Connected) setVoiceState("active");
        if (state === ConnectionState.Disconnected) {
          setVoiceState("idle");
          setAgentSpeaking(false);
        }
        if (state === ConnectionState.Reconnecting) setVoiceState("connecting");
      });

      // Play agent audio as soon as a track arrives
      room.on(
        RoomEvent.TrackSubscribed,
        (_track, pub: RemoteTrackPublication, participant: RemoteParticipant) =>
          attachTrack(pub, participant),
      );
      room.on(
        RoomEvent.TrackUnsubscribed,
        (_track, pub: RemoteTrackPublication) => detachTrack(pub),
      );

      // Speaking indicator — driven by the agent participant's audio level
      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const agentIsSpeaking = speakers.some(
          (p) => p instanceof RemoteParticipant,
        );
        setAgentSpeaking(agentIsSpeaking);
      });

      room.on(RoomEvent.Disconnected, () => {
        cleanup();
        setVoiceState("idle");
      });

      // Join and publish the local microphone
      await room.connect(url, token);
      await room.localParticipant.setMicrophoneEnabled(true);
    } catch (err) {
      cleanup();
      const msg = err instanceof Error ? err.message : "Failed to start voice session";
      setErrorMessage(msg);
      setVoiceState("error");
    }
  }, [customerId, voiceState, attachTrack, detachTrack, cleanup]);

  // ── disconnect ────────────────────────────────────────────────────────────
  const disconnect = useCallback(() => {
    cleanup();
    setVoiceState("idle");
    setAgentSpeaking(false);
    setIsMuted(false);
  }, [cleanup]);

  // ── mute toggle ───────────────────────────────────────────────────────────
  const toggleMute = useCallback(() => {
    const room = roomRef.current;
    if (!room) return;
    const next = !isMuted;
    room.localParticipant.setMicrophoneEnabled(!next);
    setIsMuted(next);
  }, [isMuted]);

  return {
    voiceState,
    isMuted,
    agentSpeaking,
    errorMessage,
    connect,
    disconnect,
    toggleMute,
  };
}
