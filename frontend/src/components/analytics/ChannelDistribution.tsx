import React from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface ChannelDistributionProps {
  data: Record<string, number> | undefined;
}

const MOCK_DATA: Record<string, number> = {
  SMS: 156,
  EMAIL: 234,
};

const CHANNEL_COLORS: Record<string, string> = {
  SMS: '#2196f3',
  EMAIL: '#9c27b0',
};

const DEFAULT_COLORS = ['#2196f3', '#9c27b0', '#ff9800', '#4caf50', '#f44336'];

interface PieLabelProps {
  name: string;
  percent: number;
  x: number;
  y: number;
  midAngle: number;
}

const renderLabel = ({ name, percent }: PieLabelProps) =>
  `${name} ${(percent * 100).toFixed(0)}%`;

const ChannelDistribution: React.FC<ChannelDistributionProps> = ({ data }) => {
  const rawData = data && Object.keys(data).length > 0 ? data : MOCK_DATA;

  const chartData = Object.entries(rawData).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Channel Distribution
        </Typography>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              dataKey="value"
              label={renderLabel}
            >
              {chartData.map((entry, index) => (
                <Cell
                  key={entry.name}
                  fill={
                    CHANNEL_COLORS[entry.name] ??
                    DEFAULT_COLORS[index % DEFAULT_COLORS.length]
                  }
                />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

export default ChannelDistribution;
