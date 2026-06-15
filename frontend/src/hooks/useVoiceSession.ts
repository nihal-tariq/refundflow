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
  RemoteParticipant,
  RemoteTrack,
  RemoteTrackPublication,
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
  // trackSid → <audio> element — cleaned up on leave/unmount
  const audioEls = useRef<Map<string, HTMLAudioElement>>(new Map());

  // ── cleanup ────────────────────────────────────────────────────────────────
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

  // ── attach a single remote audio track to the DOM ─────────────────────────
  //
  // FIX 1: Use the `track` argument from the event (the live RemoteTrack
  //         object), NOT `pub.track` which can be undefined when the event fires.
  const attachRemoteAudio = useCallback(
    (track: RemoteTrack, pub: RemoteTrackPublication) => {
      if (track.kind !== Track.Kind.Audio) return;
      if (audioEls.current.has(pub.trackSid)) return; // already attached

      const el = track.attach();
      el.autoplay = true;

      // Force play — handles browsers that ignore the autoplay attribute
      // (the user gesture on the connect button counts as an activation)
      el.play().catch(() => {
        // A failed play is non-fatal; the audio element remains attached
        // and will play as soon as the browser's autoplay policy allows it.
      });

      document.body.appendChild(el);
      audioEls.current.set(pub.trackSid, el);
    },
    [],
  );

  const detachRemoteAudio = useCallback((pub: RemoteTrackPublication) => {
    const el = audioEls.current.get(pub.trackSid);
    if (el) {
      el.pause();
      el.srcObject = null;
      el.remove();
      audioEls.current.delete(pub.trackSid);
    }
  }, []);

  // FIX 2: Attach any audio tracks already published by a participant.
  //         Called immediately after connect() to catch the agent if it joined
  //         the room before us.
  const attachExistingTracks = useCallback(
    (room: Room) => {
      room.remoteParticipants.forEach((participant) => {
        participant.trackPublications.forEach((pub) => {
          if (
            pub.kind === Track.Kind.Audio &&
            pub.isSubscribed &&
            pub.track
          ) {
            attachRemoteAudio(pub.track as RemoteTrack, pub as RemoteTrackPublication);
          }
        });
      });
    },
    [attachRemoteAudio],
  );

  // ── connect ────────────────────────────────────────────────────────────────
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

      // ── event wiring ──────────────────────────────────────────────────────
      room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
        if (state === ConnectionState.Connected) setVoiceState("active");
        if (state === ConnectionState.Disconnected) {
          setVoiceState("idle");
          setAgentSpeaking(false);
        }
        if (state === ConnectionState.Reconnecting) setVoiceState("connecting");
      });

      // FIX 1: Use the `track` argument, not pub.track
      room.on(
        RoomEvent.TrackSubscribed,
        (track: RemoteTrack, pub: RemoteTrackPublication) =>
          attachRemoteAudio(track, pub),
      );
      room.on(
        RoomEvent.TrackUnsubscribed,
        (_track: RemoteTrack, pub: RemoteTrackPublication) =>
          detachRemoteAudio(pub),
      );

      // Speaking indicator
      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        const agentSpeaks = speakers.some((p) => p instanceof RemoteParticipant);
        setAgentSpeaking(agentSpeaks);
      });

      room.on(RoomEvent.Disconnected, () => {
        cleanup();
        setVoiceState("idle");
      });

      // Join the room and enable the microphone
      await room.connect(url, token);

      // FIX 3: Explicitly unlock audio context — required in Chrome/Safari
      // when the AudioContext is created in a non-gesture context.
      await room.startAudio();

      // FIX 2: Catch tracks published before our subscription events fired
      attachExistingTracks(room);

      // Enable mic after audio context is unlocked
      await room.localParticipant.setMicrophoneEnabled(true);
    } catch (err) {
      cleanup();
      const msg = err instanceof Error ? err.message : "Failed to start voice session";
      setErrorMessage(msg);
      setVoiceState("error");
    }
  }, [customerId, voiceState, attachRemoteAudio, detachRemoteAudio, attachExistingTracks, cleanup]);

  // ── disconnect ─────────────────────────────────────────────────────────────
  const disconnect = useCallback(() => {
    cleanup();
    setVoiceState("idle");
    setAgentSpeaking(false);
    setIsMuted(false);
  }, [cleanup]);

  // ── mute toggle ────────────────────────────────────────────────────────────
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
