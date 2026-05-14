import React from 'react';
import { useAssistantStore } from '../state/assistantStore';
import { motion, AnimatePresence } from 'framer-motion';

const AssistantStatusLine = () => {
  const { statusMessage } = useAssistantStore();

  return (
    <div className="h-6 flex items-center justify-center">
      <AnimatePresence mode="wait">
        {statusMessage && (
          <motion.div
            key={statusMessage}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="text-[10px] uppercase tracking-[0.2em] text-jarvis-cyan font-mono"
          >
            {statusMessage}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default AssistantStatusLine;
