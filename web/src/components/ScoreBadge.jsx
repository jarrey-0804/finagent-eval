import React from 'react';
import { Tag } from 'antd';

const ratingConfig = {
  S: { color: 'gold', label: 'S 级' },
  A: { color: 'green', label: 'A 级' },
  B: { color: 'blue', label: 'B 级' },
  C: { color: 'orange', label: 'C 级' },
  D: { color: 'red', label: 'D 级' },
};

const ScoreBadge = ({ rating, score }) => {
  const config = ratingConfig[rating] || ratingConfig['C'];

  return (
    <Tag
      color={config.color}
      style={{
        fontSize: 14,
        padding: '2px 12px',
        fontWeight: 600,
        borderRadius: 4,
      }}
    >
      {config.label} {score !== undefined ? `(${score})` : ''}
    </Tag>
  );
};

export default ScoreBadge;
