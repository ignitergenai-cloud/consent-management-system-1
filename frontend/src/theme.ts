import { createTheme } from '@mui/material/styles';

declare module '@mui/material/styles' {
  interface Palette {
    consent: {
      granted: string;
      denied: string;
      pending: string;
      expired: string;
    };
  }
  interface PaletteOptions {
    consent?: {
      granted?: string;
      denied?: string;
      pending?: string;
      expired?: string;
    };
  }
}

export const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    consent: {
      granted: '#4caf50',
      denied: '#f44336',
      pending: '#ff9800',
      expired: '#9e9e9e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
  typography: {
    h4: {
      fontWeight: 600,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 6,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 600,
        },
      },
    },
  },
});
