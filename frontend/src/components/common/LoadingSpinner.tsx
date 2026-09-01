import { Box, CircularProgress, Typography } from '@mui/material';

export function LoadingSpinner({ message }: { message?: string }) {
  return (
    <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" minHeight={200}>
      <CircularProgress />
      {message && <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>{message}</Typography>}
    </Box>
  );
}
