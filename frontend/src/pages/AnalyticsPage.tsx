import Box from '@mui/material/Box';

import { PageHeader } from '../components/common/PageHeader';
import AnalyticsDashboard from '../components/analytics/AnalyticsDashboard';

export function AnalyticsPage() {
  return (
    <Box>
      <PageHeader
        title="Analytics"
        subtitle="Consent analytics and insights"
      />
      <AnalyticsDashboard />
    </Box>
  );
}
