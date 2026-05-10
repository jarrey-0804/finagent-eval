import { useState, useEffect, useCallback } from 'react';
import { message } from 'antd';
import { evaluationApi, agentApi, reportApi, systemApi } from '../api';

// Generic hook for API calls with loading state and error handling
export const useApiCall = (apiFn, immediate = false) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState(null);

  const execute = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFn(...args);
      setData(result);
      return result;
    } catch (err) {
      const errorMsg = err.response?.data?.message || err.message || '请求失败';
      setError(errorMsg);
      message.error(errorMsg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [apiFn]);

  return { data, loading, error, execute, setData };
};

// Hook for fetching evaluation list
export const useEvaluations = (params = {}) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const result = await evaluationApi.list(params);
      setData(result.evaluations || result || []);
    } catch (err) {
      setError(err);
      // Fallback to empty array on error
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetch(); }, [fetch]);

  return { data, loading, error, refetch: fetch, setData };
};

// Hook for fetching single evaluation
export const useEvaluation = (id) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    evaluationApi.detail(id)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [id]);

  return { data, loading, setData };
};

// Hook for fetching agents
export const useAgents = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    agentApi.list()
      .then(result => setData(result.agents || result || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, setData };
};

// Hook for system health
export const useSystemHealth = () => {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      systemApi.health(),
      systemApi.ready(),
    ])
      .then(([healthResult, readyResult]) => {
        setHealth({
          ...healthResult,
          ready: readyResult,
        });
      })
      .catch(() => setHealth(null))
      .finally(() => setLoading(false));
  }, []);

  return { health, loading };
};

// Hook for system info (stats)
export const useSystemInfo = () => {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    systemApi.info()
      .then(setInfo)
      .catch(() => setInfo(null))
      .finally(() => setLoading(false));
  }, []);

  return { info, loading };
};

// Hook for reports
export const useReports = (params = {}) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const result = await reportApi.list(params);
      setData(result.reports || result || []);
    } catch (err) {
      setError(err);
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => { fetch(); }, [fetch]);

  return { data, loading, error, refetch: fetch, setData };
};

// Export API functions for direct use
export { evaluationApi, agentApi, reportApi, systemApi };
