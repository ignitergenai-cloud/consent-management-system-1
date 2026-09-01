import React from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

import type { ConsentStatus } from '../../api/types';
import { CONSENT_STATUS_COLORS } from '../../utils/constants';

interface StatusBreakdownProps {
  data: Record<string, number> | undefined;
}

const MOCK_DATA: Record<string, number> = {
  GRANTED: 320,
  DENIED: 45,
  PENDING: 28,
  EXPIRED: 67,
  REVOKED: 15,
  FAILED: 8,
};

const StatusBreakdown: React.FC<StatusBreakdownProps> = ({ data }) => {
  const rawData = data && Object.keys(data).length > 0 ? data : MOCK_DATA;

  const chartData = Object.entries(rawData).map(([status, count]) => ({
    status,
    count,
  }));

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Status Breakdown
        </Typography>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="status" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count">
              {chartData.map((entry) => (
                <Cell
                  key={entry.status}
                  fill={
                    CONSENT_STATUS_COLORS[entry.status as ConsentStatus] ??
                    '#9e9e9e'
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

export default StatusBreakdown;
