import React, { useState } from 'react';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
  Typography,
  Divider,
  IconButton,
  ListItem,
  ListItemIcon,
  ListItemText
} from '@mui/material';
import {
  Menu as MenuIcon,
  People as PeopleIcon,
  Assignment as AssignmentIcon,
  ExitToApp as LogoutIcon
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import AttendanceManagement from './AttendanceManagement';
import AssignmentManagement from './AssignmentManagement';

const TeacherDashboard = () => {
  const [currentComponent, setCurrentComponent] = useState('attendance');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('user');
    navigate('/');
  };

  const menuItems = [
    { text: 'Attendance Management', icon: <PeopleIcon />, component: 'attendance' },
    { text: 'Assignment Management', icon: <AssignmentIcon />, component: 'assignments' },
    { text: 'Logout', icon: <LogoutIcon />, action: handleLogout }
  ];

  const renderComponent = () => {
    switch(currentComponent) {
      case 'attendance':
        return <AttendanceManagement />;
      case 'assignments':
        return <AssignmentManagement />;
      default:
        return <AttendanceManagement />;
    }
  };
  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box sx={{ display: 'flex' }}>
        <AppBar position="fixed">
          <Toolbar>
            <IconButton
              color="inherit"
              edge="start"
              onClick={() => setDrawerOpen(!drawerOpen)}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" noWrap sx={{ flexGrow: 1 }}>
              Teacher Dashboard
            </Typography>
          </Toolbar>
        </AppBar>

        <Drawer
          variant="temporary"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
        >
          <Toolbar />
          <Divider />
          <List>
            {menuItems.map((item) => (
              <ListItem
                button
                key={item.text}
                onClick={() => {
                  if (item.action) {
                    item.action();
                  } else {
                    setCurrentComponent(item.component);
                    setDrawerOpen(false);
                  }
                }}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.text} />
              </ListItem>
            ))}
          </List>
        </Drawer>

        <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
          <Toolbar />
          {renderComponent()}
        </Box>
      </Box>
    </LocalizationProvider>
  );
};

export default TeacherDashboard;