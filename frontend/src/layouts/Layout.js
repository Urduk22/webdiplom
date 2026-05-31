import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { AppBar, Toolbar, Typography, Button, IconButton, Drawer, List, ListItem, ListItemText, Box, Container, useMediaQuery, useTheme } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import { Link, useNavigate } from 'react-router-dom';

export default function Layout({ children }) {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const [drawerOpen, setDrawerOpen] = useState(false);

    const menuItems = user ? [
        { label: 'Главная', path: '/' },
        { label: 'Мои опросы', path: '/surveys' },
        { label: 'Создать', path: '/create-survey' },
        { label: 'Импорт', path: '/import-survey' },
        { label: `Выйти (${user.username})`, action: logout }
    ] : [
        { label: 'Главная', path: '/' },
        { label: 'Вход', path: '/login' },
        { label: 'Регистрация', path: '/register' }
    ];

    const handleMenuClick = (item) => {
        if (item.action) {
            item.action();
            if (isMobile) setDrawerOpen(false);
            navigate('/');
        } else if (item.path) {
            navigate(item.path);
            if (isMobile) setDrawerOpen(false);
        }
    };

    return (
        <>
            <AppBar position="static">
                <Toolbar>
                    <Typography variant="h6" sx={{ flexGrow: 1 }}>
                        Анализ опросов
                    </Typography>
                    {isMobile ? (
                        <>
                            <IconButton color="inherit" onClick={() => setDrawerOpen(true)}>
                                <MenuIcon />
                            </IconButton>
                            <Drawer anchor="right" open={drawerOpen} onClose={() => setDrawerOpen(false)}>
                                <Box sx={{ width: 250 }} role="presentation" onClick={() => setDrawerOpen(false)}>
                                    <List>
                                        {menuItems.map((item, idx) => (
                                            <ListItem button key={idx} onClick={() => handleMenuClick(item)}>
                                                <ListItemText primary={item.label} />
                                            </ListItem>
                                        ))}
                                    </List>
                                </Box>
                            </Drawer>
                        </>
                    ) : (
                        <Box sx={{ display: 'flex', gap: 2 }}>
                            {menuItems.map((item, idx) => (
                                item.action ? (
                                    <Button color="inherit" key={idx} onClick={item.action}>
                                        {item.label}
                                    </Button>
                                ) : (
                                    <Button color="inherit" key={idx} component={Link} to={item.path}>
                                        {item.label}
                                    </Button>
                                )
                            ))}
                        </Box>
                    )}
                </Toolbar>
            </AppBar>
            <Container sx={{ mt: 4, mb: 4 }}>
                {children}
            </Container>
        </>
    );
}