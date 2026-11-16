import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchParticipantSession,
  loginParticipant,
  logoutParticipant,
  type ParticipantLoginPayload,
  type ParticipantSession
} from "./api";

export type { ParticipantLoginPayload, ParticipantSession };

export const participantSessionQueryKey = ["participant", "session"] as const;

const LOGGED_OUT_SESSION: ParticipantSession = {
  authenticated: false,
  team_id: null,
  team_name: null
};

export function useParticipantSession() {
  return useQuery({
    queryKey: participantSessionQueryKey,
    queryFn: fetchParticipantSession,
    staleTime: 30_000
  });
}

export function useParticipantLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: loginParticipant,
    onSuccess: (session) => {
      queryClient.setQueryData(participantSessionQueryKey, session);
    }
  });
}

export function useParticipantLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logoutParticipant,
    onSuccess: () => {
      queryClient.setQueryData(participantSessionQueryKey, LOGGED_OUT_SESSION);
    }
  });
}
