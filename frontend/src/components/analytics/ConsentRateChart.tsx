import React from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { format, parseISO } from 'date-fns';

interface DailyCount {
  date: string;
  granted: number;
  denied: number;
}

interface ConsentRateChartProps {
  data: DailyCount[] | undefined;
}

const MOCK_DATA: DailyCount[] = [
  { date: '2025-01-01', granted: 45, denied: 12 },
  { date: '2025-01-02', granted: 52, denied: 8 },
  { date: '2025-01-03', granted: 38, denied: 15 },
  { date: '2025-01-04', granted: 65, denied: 10 },
  { date: '2025-01-05', granted: 48, denied: 14 },
  { date: '2025-01-06', granted: 55, denied: 7 },
  { date: '2025-01-07', granted: 70, denied: 11 },
  { date: '2025-01-08', granted: 62, denied: 9 },
  { date: '2025-01-09', granted: 58, denied: 13 },
  { date: '2025-01-10', granted: 72, denied: 6 },
  { date: '2025-01-11', granted: 68, denied: 8 },
  { date: '2025-01-12', granted: 75, denied: 5 },
  { date: '2025-01-13', granted: 60, denied: 12 },
  { date: '2025-01-14', granted: 80, denied: 4 },
];

function formatTickDate(dateString: string): string {
  try {
    return format(parseISO(dateString), 'MMM d');
  } catch {
    return dateString;
  }
}

const ConsentRateChart: React.FC<ConsentRateChartProps> = ({ data }) => {
  const chartData = data && data.length > 0 ? data : MOCK_DATA;

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Consent Rate Over Time
        </Typography>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tickFormatter={formatTickDate} />
            <YAxis />
            <Tooltip
              labelFormatter={(label: string) => formatTickDate(label)}
            />
            <Legend />
            <Area
              type="monotone"
              dataKey="granted"
              stroke="#4caf50"
              fill="#4caf50"
              fillOpacity={0.3}
            />
            <Area
              type="monotone"
              dataKey="denied"
              stroke="#f44336"
              fill="#f44336"
              fillOpacity={0.3}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

export default ConsentRateChart;
