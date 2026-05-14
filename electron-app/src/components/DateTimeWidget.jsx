import React, { useState, useEffect } from 'react';

const DateTimeWidget = () => {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const hours = time.getHours().toString().padStart(2, '0');
  const minutes = time.getMinutes().toString().padStart(2, '0');
  const seconds = time.getSeconds().toString().padStart(2, '0');
  
  const dateOpts = { weekday: 'short', month: 'short', day: '2-digit', year: 'numeric' };
  const dateStr = time.toLocaleDateString('en-US', dateOpts).toUpperCase();

  return (
    <div className="flex flex-col items-end text-white font-mono opacity-80">
      <div className="text-5xl font-light tracking-wider flex items-center">
        <span>{hours}</span>
        <span className="text-jarvis-cyan mx-1 animate-pulse opacity-50">:</span>
        <span>{minutes}</span>
        <span className="text-xl ml-2 text-white/40 tracking-widest">{seconds}</span>
      </div>
      <div className="text-xs uppercase tracking-[0.3em] text-white/50 mt-1">
        {dateStr}
      </div>
    </div>
  );
};

export default DateTimeWidget;
