import React, { useRef } from 'react';
import { Button } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';

export default function FileUploadButton({ onFileSelect, accept, children }) {
    const fileInputRef = useRef(null);

    const handleClick = () => {
        fileInputRef.current.click();
    };

    const handleChange = (event) => {
        const file = event.target.files[0];
        if (file && onFileSelect) {
            onFileSelect(file);
        }
    };

    return (
        <>
            <input
                type="file"
                ref={fileInputRef}
                style={{ display: 'none' }}
                accept={accept}
                onChange={handleChange}
            />
            <Button
                variant="contained"
                startIcon={<CloudUploadIcon />}
                onClick={handleClick}
            >
                {children || 'Загрузить файл'}
            </Button>
        </>
    );
}