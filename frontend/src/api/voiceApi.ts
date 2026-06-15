/**
 * Voice API — fetches a LiveKit access token from the backend.
 */

import { apiPost } from "./client";

export interface VoiceTokenResponse {
  token: string;
  url: string;
  room_name: string;
}

export function fetchVoiceToken(customerId: string): Promise<VoiceTokenResponse> {
  return apiPost<VoiceTokenResponse>("/voice/token", { customer_id: customerId });
}
