import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests/browser',timeout:60000,use:{baseURL:'http://127.0.0.1:4173/asset_analysis/',browserName:'chromium',...(process.env.STATIC_TEST_EDGE==='1'?{channel:'msedge'}:{})},webServer:{command:'npm run preview -- --port 4173',url:'http://127.0.0.1:4173/asset_analysis/',reuseExistingServer:true},reporter:'list'});
