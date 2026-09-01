import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import CircleIcon from '@mui/icons-material/Circle';

import { useHealthStatus } from '../api/analytics';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { PageHeader } from '../components/common/PageHeader';

function formatUptime(seconds: number | undefined): string {
  if (seconds === undefined || seconds === null) return 'N/A';
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  parts.push(`${minutes}m`);
  return parts.join(' ');
}

export function SettingsPage() {
  const {
    data: health,
    isLoading: healthLoading,
    error: healthError,
  } = useHealthStatus();

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
  const environment = import.meta.env.MODE || 'development';
  const appVersion = '0.1.0';

  const isHealthy = health?.status === 'healthy' || health?.status === 'ok';

  return (
    <Box>
      <PageHeader
        title="Settings"
        subtitle="System configuration"
      />

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Status
              </Typography>

              {healthLoading ? (
                <LoadingSpinner message="Checking system health..." />
              ) : healthError ? (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  Unable to reach the API. The backend service may be unavailable.
                </Alert>
              ) : (
                <>
                  <List disablePadding>
                    <ListItem divider>
                      <ListItemText
                        primary="Status"
                        secondary={
                          <Box
                            component="span"
                            sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}
                          >
                            <CircleIcon
                              sx={{
                                fontSize: 12,
                                color: isHealthy ? 'success.main' : 'error.main',
                              }}
                            />
                            {health?.status ?? 'Unknown'}
                          </Box>
                        }
                      />
                    </ListItem>
                    <ListItem divider>
                      <ListItemText
                        primary="Version"
                        secondary={health?.version ?? 'N/A'}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary="Uptime"
                        secondary={formatUptime(health?.uptime_seconds)}
                      />
                    </ListItem>
                  </List>

                  {health?.checks && Object.keys(health.checks).length > 0 && (
                    <Box sx={{ mt: 3 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        Health Checks
                      </Typography>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Service</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell align="right">Latency (ms)</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {Object.entries(health.checks).map(([name, check]) => (
                            <TableRow key={name}>
                              <TableCell>{name}</TableCell>
                              <TableCell>
                                <Chip
                                  label={check.status}
                                  size="small"
                                  color={
                                    check.status === 'healthy' || check.status === 'ok'
                                      ? 'success'
                                      : check.status === 'degraded'
                                        ? 'warning'
                                        : 'error'
                                  }
                                  variant="outlined"
                                />
                              </TableCell>
                              <TableCell align="right">
                                {check.latency_ms !== undefined
                                  ? `${check.latency_ms}`
                                  : 'N/A'}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </Box>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Configuration
              </Typography>
              <List disablePadding>
                <ListItem divider>
                  <ListItemText
                    primary="API Base URL"
                    secondary={apiBaseUrl}
                  />
                </ListItem>
                <ListItem divider>
                  <ListItemText
                    primary="Environment"
                    secondary={environment}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="App Version"
                    secondary={appVersion}
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
