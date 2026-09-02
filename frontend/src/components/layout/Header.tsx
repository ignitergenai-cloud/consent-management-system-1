import { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AppBar, Box, IconButton, Toolbar, Tooltip, Typography } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import LogoutIcon from '@mui/icons-material/Logout';
import { useAuth } from '../../context/AuthContext';

interface HeaderProps {
  drawerWidth: number;
  onMenuToggle: () => void;
}

const PAGE_NAMES: Record<string, string> = {
  '/': 'Dashboard',
  '/consents': 'Consents',
  '/analytics': 'Analytics',
  '/settings': 'Settings',
};

function getPageName(pathname: string): string {
  if (PAGE_NAMES[pathname]) return PAGE_NAMES[pathname];
  const match = Object.entries(PAGE_NAMES).find(
    ([path]) => path !== '/' && pathname.startsWith(path),
  );
  return match ? match[1] : 'Consent Management System';
}

export function Header({ drawerWidth, onMenuToggle }: HeaderProps) {
  const location = useLocation();
  const navigate  = useNavigate();
  const { user, logout } = useAuth();
  const pageName = useMemo(() => getPageName(location.pathname), [location.pathname]);

  const handleLogout = () => {
    logout();
    void navigate('/login');
  };

  return (
    <AppBar
      position="fixed"
      sx={{
        width: { sm: `calc(100% - ${drawerWidth}px)` },
        ml: { sm: `${drawerWidth}px` },
      }}
    >
      <Toolbar>
        <IconButton
          color="inherit"
          edge="start"
          onClick={onMenuToggle}
          sx={{ mr: 2, display: { sm: 'none' } }}
        >
          <MenuIcon />
        </IconButton>

        <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
          {pageName}
        </Typography>

        {/* System status indicator */}
        <Box
          sx={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            bgcolor: 'success.main',
            mr: 2,
          }}
        />

        {user && (
          <Typography variant="body2" sx={{ mr: 1, opacity: 0.85 }}>
            {user.name}
          </Typography>
        )}

        <Tooltip title="Logout">
          <IconButton color="inherit" onClick={handleLogout} aria-label="logout">
            <LogoutIcon />
          </IconButton>
        </Tooltip>
      </Toolbar>
    </AppBar>
  );
}
