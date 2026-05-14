import { useState, useCallback } from 'react';

export const useDoubleClick = (callback, delay = 300) => {
  const [clickTimer, setClickTimer] = useState(null);
  
  const handleClick = useCallback(() => {
    if (clickTimer) {
      clearTimeout(clickTimer);
      setClickTimer(null);
      callback();
    } else {
      const timer = setTimeout(() => {
        setClickTimer(null);
      }, delay);
      setClickTimer(timer);
    }
  }, [callback, delay, clickTimer]);
  
  return handleClick;
};