import { useState, useEffect, useCallback } from 'react';
import { useAssistantStore } from '../state/assistantStore';

const BACKEND_URL = 'http://127.0.0.1:8000';

export const useLiveContext = () => {
  const { setLiveContextData, setProviderStatus, setConnectionHealth } = useAssistantStore();
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchLiveContext = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${BACKEND_URL}/api/v1/system/status`);
      if (!response.ok) throw new Error('Failed to fetch live context');

      const data = await response.json();
      setContext(data);
      setLiveContextData(data);

      if (data.providers) {
        setProviderStatus('nvidia', data.providers.nvidia === 'online' ? 'online' : 'missing_key');
        setProviderStatus('gemini', data.providers.gemini === 'online' ? 'online' : 'missing_key');
      }

      setConnectionHealth('good');
    } catch (err) {
      setError(err.message);
      setConnectionHealth('offline');
      setProviderStatus('nvidia', 'offline');
      setProviderStatus('gemini', 'offline');
    } finally {
      setLoading(false);
    }
  }, [setLiveContextData, setProviderStatus, setConnectionHealth]);

  const fetchContextData = useCallback(async (query) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/v1/context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });

      if (!response.ok) throw new Error('Failed to fetch context data');

      const data = await response.json();
      return data;
    } catch (err) {
      console.error('Context fetch error:', err);
      return null;
    }
  }, []);

  useEffect(() => {
    fetchLiveContext();
    const interval = setInterval(fetchLiveContext, 60000);
    return () => clearInterval(interval);
  }, [fetchLiveContext]);

  return { context, loading, error, refetch: fetchLiveContext, fetchContextData };
};
