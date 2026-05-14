import { useState, useEffect } from 'react';
import { useAssistantStore } from '../state/assistantStore';

export const useClock = () => {
  const [time, setTime] = useState(new Date());
  const [date, setDate] = useState(new Date());
  
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(now);
      setDate(now);
      useAssistantStore.getState().setMode(useAssistantStore.getState().mode);
    };
    
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);
  
  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: true 
    });
  };
  
  const formatDate = (date) => {
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    });
  };
  
  return {
    time: formatTime(time),
    date: formatDate(date),
    rawTime: time,
    rawDate: date
  };
};