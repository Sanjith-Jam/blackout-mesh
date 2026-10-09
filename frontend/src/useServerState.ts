import { useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getWebSocketUrl, fetchSnapshot } from './api';
import { WebSocketEnvelope } from './types';
import { useAppStore } from './store';

export function useWebSocketSync() {
  const queryClient = useQueryClient();
  const setConnected = useAppStore(s => s.setConnected);
  const setStale = useAppStore(s => s.setStale);
  
  const currentRunId = useRef<string | null>(null);
  const currentEpoch = useRef<number | null>(null);
  const currentRevision = useRef<number>(-1);
  const reconnectAttempts = useRef<number>(0);

  // We only use useQuery for the initial fetch and explicit resyncs.
  // The query function must support cancellation if an older HTTP response arrives after a newer WS message.
  const query = useQuery({
    queryKey: ['snapshot'],
    queryFn: async ({ signal }) => {
      const data = await fetchSnapshot(signal);
      return data;
    },
    refetchInterval: false,
    refetchOnWindowFocus: true,
  });

  useEffect(() => {
    let disposed = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let heartbeatTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      if (disposed) return;
      
      const wsUrl = getWebSocketUrl('/ws/live');
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (disposed) return;
        setConnected(true);
        setStale(false);
        reconnectAttempts.current = 0;
      };

      ws.onmessage = (event) => {
        if (disposed) return;
        try {
          const envelope: WebSocketEnvelope = JSON.parse(event.data);
          if (!envelope || typeof envelope !== 'object' || envelope.type !== 'snapshot' || !envelope.payload) return;
          
          const data = envelope.payload;
          const identity = data.contract?.identity;
          if (!identity) return;

          const isNewEpochOrRun = currentRunId.current !== identity.run_id || currentEpoch.current !== identity.server_epoch;
          const isGap = !isNewEpochOrRun && data.control_revision > currentRevision.current + 1;
          const isStale = !isNewEpochOrRun && data.control_revision <= currentRevision.current;

          if (isStale) {
             // reject duplicate or out of order
             return;
          }

          if (isNewEpochOrRun || isGap) {
             // explicitly resync on epoch/run change or gaps
             queryClient.cancelQueries({ queryKey: ['snapshot'] });
             queryClient.invalidateQueries({ queryKey: ['snapshot'] });
          }

          currentRunId.current = identity.run_id;
          currentEpoch.current = identity.server_epoch;
          currentRevision.current = data.control_revision;
          
          // update cache, cancelling any ongoing fetch that might be stale
          queryClient.cancelQueries({ queryKey: ['snapshot'] });
          queryClient.setQueryData(['snapshot'], data);
          setStale(false);

          // Heartbeat check: mark stale if no message in 1000ms
          clearTimeout(heartbeatTimer);
          heartbeatTimer = setTimeout(() => {
             if (!disposed) setStale(true);
          }, 1000);

        } catch (e) {
          // parse error
        }
      };

      ws.onclose = () => {
        if (disposed) return;
        setConnected(false);
        setStale(true);
        
        // Capped backoff + jitter
        const attempts = reconnectAttempts.current;
        const delay = Math.min(1000 * Math.pow(1.5, attempts), 10000) + Math.random() * 500;
        reconnectAttempts.current++;
        reconnectTimer = setTimeout(connect, delay);
      };
      
      ws.onerror = () => {
        // handled by onclose
      };
    };

    connect();

    return () => {
      disposed = true;
      if (ws) {
        ws.onopen = null;
        ws.onmessage = null;
        ws.onclose = null;
        ws.onerror = null;
        ws.close();
      }
      clearTimeout(reconnectTimer);
      clearTimeout(heartbeatTimer);
      setConnected(false);
      setStale(true);
    };
  }, [queryClient, setConnected, setStale]);

  return query;
}

export function useSnapshot() {
  return useQuery({
    queryKey: ['snapshot'],
    queryFn: async ({ signal }) => fetchSnapshot(signal),
    refetchInterval: false,
    refetchOnWindowFocus: true,
  });
}
