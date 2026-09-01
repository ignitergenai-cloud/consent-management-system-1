import { useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CardActions from '@mui/material/CardActions';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import AddIcon from '@mui/icons-material/Add';
import BarChartIcon from '@mui/icons-material/BarChart';

import { useConsents } from '../api/consents';
import { useConsentAnalytics } from '../api/analytics';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { PageHeader } from '../components/common/PageHeader';
import KPICards from '../components/analytics/KPICards';
import { ConsentStatusChip } from '../components/consents/ConsentStatusChip';
import { truncateId, formatDate } from '../utils/formatters';

export function DashboardPage() {
  const navigate = useNavigate();

  const {
    data: consentsData,
    isLoading: consentsLoading,
    error: consentsError,
    refetch: refetchConsents,
  } = useConsents({ page: 1, page_size: 10 });

  const {
    data: analytics,
    isLoading: analyticsLoading,
    error: analyticsError,
    refetch: refetchAnalytics,
  } = useConsentAnalytics();

  const isLoading = consentsLoading && analyticsLoading;
  const criticalError = consentsError && analyticsError;

  if (isLoading) {
    return <LoadingSpinner message="Loading dashboard..." />;
  }

  if (criticalError) {
    return (
      <ErrorAlert
        title="Failed to load dashboard"
        message="Unable to fetch dashboard data. Please check your connection and try again."
        onRetry={() => {
          refetchConsents();
          refetchAnalytics();
        }}
      />
    );
  }

  const recentConsents = consentsData?.items ?? [];

  return (
    <Box>
      <PageHeader
        title="Dashboard"
        subtitle="Consent Management System Overview"
      />

      <Box sx={{ mb: 3 }}>
        <KPICards analytics={analytics} />
      </Box>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Consents
              </Typography>

              {consentsLoading ? (
                <LoadingSpinner message="Loading consents..." />
              ) : consentsError ? (
                <ErrorAlert
                  message="Failed to load recent consents."
                  onRetry={() => refetchConsents()}
                />
              ) : recentConsents.length === 0 ? (
                <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                  No consent records found.
                </Typography>
              ) : (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>ID</TableCell>
                      <TableCell>Customer</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Date</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {recentConsents.map((consent) => (
                      <TableRow
                        key={consent.consent_id}
                        hover
                        sx={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/consents/${consent.consent_id}`)}
                      >
                        <TableCell>
                          <Typography variant="body2" fontFamily="monospace">
                            {truncateId(consent.consent_id)}
                          </Typography>
                        </TableCell>
                        <TableCell>{consent.customer_id}</TableCell>
                        <TableCell>{consent.consent_type}</TableCell>
                        <TableCell>
                          <ConsentStatusChip status={consent.status} />
                        </TableCell>
                        <TableCell>{formatDate(consent.created_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
            <CardActions sx={{ justifyContent: 'flex-end', px: 2, pb: 2 }}>
              <Button size="small" onClick={() => navigate('/consents')}>
                View All
              </Button>
            </CardActions>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Quick Actions
              </Typography>
              <Stack spacing={2}>
                <Button
                  variant="outlined"
                  startIcon={<AddIcon />}
                  fullWidth
                  onClick={() => navigate('/consents', { state: { openForm: true } })}
                >
                  Create Consent
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<BarChartIcon />}
                  fullWidth
                  onClick={() => navigate('/analytics')}
                >
                  View Analytics
                </Button>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
