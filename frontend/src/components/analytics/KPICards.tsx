import React from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import AssignmentIcon from '@mui/icons-material/Assignment';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';

import type { ConsentAnalytics } from '../../api/types';
import { formatPercentage } from '../../utils/formatters';

interface KPICardsProps {
  analytics: ConsentAnalytics | undefined;
}

const KPICards: React.FC<KPICardsProps> = ({ analytics }) => {
  const grantRate = analytics?.grant_rate ?? 0;

  const cards = [
    {
      title: 'Total Consents',
      value: String(analytics?.total_consents ?? 0),
      icon: <AssignmentIcon />,
      iconColor: '#2196f3',
    },
    {
      title: 'Grant Rate',
      value: formatPercentage(grantRate),
      icon: <TrendingUpIcon />,
      iconColor: '#4caf50',
      indicator: grantRate > 0.5 ? 'up' : 'down',
    },
    {
      title: 'Avg Response Time',
      value: `${(analytics?.avg_response_time_hours ?? 0).toFixed(1)}h`,
      icon: <AccessTimeIcon />,
      iconColor: '#ff9800',
    },
  ];

  return (
    <Grid container spacing={3}>
      {cards.map((card) => (
        <Grid key={card.title} size={{ xs: 12, sm: 6, md: 4 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 1 }}>
                <Box sx={{ color: card.iconColor, display: 'flex', mr: 1 }}>
                  {card.icon}
                </Box>
              </Box>
              <Typography variant="caption" color="text.secondary">
                {card.title}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                  {card.value}
                </Typography>
                {card.indicator === 'up' && (
                  <ArrowUpwardIcon sx={{ color: '#4caf50', fontSize: 20 }} />
                )}
                {card.indicator === 'down' && (
                  <ArrowDownwardIcon sx={{ color: '#f44336', fontSize: 20 }} />
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  );
};

export default KPICards;
