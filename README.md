# Global Object Detection API

This project turns your `model/best1.pt` file into a reusable API.

You can deploy it once on a server and then use the same API link from:

- any website
- Android or iOS apps
- another backend
- internal company tools

## What It Does

- loads `best1.pt` on the server
- accepts image upload or image URL
- returns detected objects, confidence, counts, and object info
- can also return an annotated image in base64
- includes CORS support, so it can be called from any frontend

## Project Structure

```text
app/
  detector.py
  main.py
  metadata.py
model/
  best1.pt
static/
  index.html
```

## Run Locally

```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:

- `http://localhost:8000/` for the demo page
- `http://localhost:8000/docs` for Swagger API docs

## API Endpoints

### `GET /health`

Checks whether the API is running.

### `GET /classes`

Returns all model labels and display info.

### `POST /detect/file`

Form-data fields:

- `file`: image file
- `conf`: confidence threshold, example `0.25`
- `iou`: IOU threshold, example `0.45`
- `include_image`: `true` or `false`

Example JavaScript:

```js
const formData = new FormData();
formData.append("file", imageFile);
formData.append("conf", "0.25");
formData.append("iou", "0.45");
formData.append("include_image", "true");

const result = await fetch("https://your-domain.com/detect/file", {
  method: "POST",
  body: formData
}).then((res) => res.json());
```

### `POST /detect/url`

JSON body:

```json
{
  "image_url": "https://example.com/sample.jpg",
  "conf": 0.25,
  "iou": 0.45,
  "include_image": true
}
```

Example JavaScript:

```js
const result = await fetch("https://your-domain.com/detect/url", {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    image_url: "https://example.com/sample.jpg",
    conf: 0.25,
    iou: 0.45,
    include_image: true
  })
}).then((res) => res.json());
```

## Example Response

```json
{
  "success": true,
  "source": "sample.jpg",
  "model_name": "best1.pt",
  "image_size": {
    "width": 1280,
    "height": 720
  },
  "total_detections": 2,
  "counts": {
    "PLASTIC": 1,
    "METAL": 1
  },
  "detections": [
    {
      "id": 1,
      "class_id": 5,
      "label": "PLASTIC",
      "confidence": 0.9421,
      "bbox": {
        "x1": 44.2,
        "y1": 81.4,
        "x2": 220.5,
        "y2": 480.8,
        "width": 176.3,
        "height": 399.4
      },
      "info": {
        "title": "Plastic",
        "category": "Dry Recyclable",
        "description": "Plastic bottles, containers, or packaging depending on local recycling rules.",
        "handling_tip": "Rinse the item and check local recycling acceptance."
      }
    }
  ],
  "detected_object_info": [
    {
      "label": "PLASTIC",
      "count": 1,
      "title": "Plastic",
      "category": "Dry Recyclable",
      "description": "Plastic bottles, containers, or packaging depending on local recycling rules.",
      "handling_tip": "Rinse the item and check local recycling acceptance."
    }
  ]
}
```

## Global Deployment

This API is not tied to one page. After deployment, one public URL can be reused everywhere.

Typical flow:

1. Deploy this project on Render, Railway, Azure, AWS, GCP, or your own VPS.
2. Keep the API URL, for example `https://detect.yourdomain.com`.
3. Call `/detect/file` or `/detect/url` from any site or mobile app.
4. Show the returned JSON on that client however you want.

Because CORS is enabled with `*`, any frontend can call it directly.

## Docker Run

```bash
docker build -t object-detection-api .
docker run -p 8000:8000 object-detection-api
```

## Azure Deployment

This repository is prepared for Azure Container Apps deployment using the included Dockerfile.

Files added for Azure:

- `azure.yaml`
- `scripts/deploy-azure.ps1`
- `.dockerignore`

### 1. Prerequisites

- Azure CLI installed
- Docker not required locally because the script uses `az acr build`
- Azure login completed with:

```bash
az login
```

### 2. Run Azure Deployment Script

From the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-azure.ps1
```

Optional example with custom names:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-azure.ps1 `
  -SubscriptionId "YOUR_SUBSCRIPTION_ID" `
  -ResourceGroup "rg-waste-detector" `
  -Location "centralindia" `
  -ContainerRegistry "acrwastedetector123" `
  -ContainerAppEnvironment "env-waste-detector" `
  -ContainerAppName "ca-waste-detector"
```

### 3. What The Script Does

- creates resource group
- creates Azure Container Registry
- builds the Docker image in Azure
- creates Container Apps environment
- creates or updates a public Container App
- prints your final public API URL

### 4. After Deployment

Use the generated Azure URL like:

- `https://your-app-url/`
- `https://your-app-url/docs`
- `https://your-app-url/detect/file`
- `https://your-app-url/detect/url`

This URL can then be used globally from any website or app.

## Azure Portal Upload Deployment

If you want to deploy through the Azure website only, use Azure App Service on Linux and upload the project ZIP.

Files used for this flow:

- `requirements.txt`
- `startup.sh`
- `app/main.py`
- `model/best1.pt`

### 1. Create the ZIP correctly

Create one ZIP file from the project root contents.

Important:

- include files and folders inside the project root
- do not zip an outer parent folder
- make sure `model/best1.pt` is inside the ZIP

Your ZIP should contain entries like:

```text
app/
model/
static/
requirements.txt
startup.sh
example_client.html
```

### 2. Create App Service in Azure Portal

In Azure Portal:

1. Open `App Services`
2. Click `Create`
3. Choose these values:
   - Publish: `Code`
   - Runtime stack: `Python 3.12`
   - Operating System: `Linux`
   - Region: your preferred region
   - Pricing plan: choose at least a plan that can handle PyTorch memory load

### 3. Configure startup command

After the App Service is created:

1. Open the App Service
2. Go to `Settings > Configuration`
3. Open `General settings`
4. In `Startup Command`, enter:

```text
startup.sh
```

5. Save

This is required for FastAPI on Azure App Service.

### 4. Enable build during deployment

In the same App Service:

1. Go to `Settings > Environment variables` or `Configuration`
2. Add this app setting:

```text
SCM_DO_BUILD_DURING_DEPLOYMENT = 1
```

3. Save

This tells Azure to install packages from `requirements.txt` during deployment.

### 5. Upload ZIP through Azure website

In the App Service:

1. Go to `Development Tools > Advanced Tools`
2. Click `Go`
3. In Kudu, open `Tools > Zip Push Deploy`
4. Drag and drop your ZIP file there

Azure will unpack and deploy the project to the app service.

### 6. Restart and verify

After upload completes:

1. Go back to the App Service overview page
2. Click `Restart`
3. Wait 1 to 3 minutes

Then open:

- `/health`
- `/docs`

Example:

```text
https://your-app-name.azurewebsites.net/health
https://your-app-name.azurewebsites.net/docs
```

### 7. If Azure shows startup or package errors

Check:

1. `Log stream` in the App Service
2. `Deployment Center` logs
3. `Advanced Tools > Debug console`

Most common causes:

- ZIP created incorrectly with one extra top-level folder
- `best1.pt` missing from `model/`
- `SCM_DO_BUILD_DURING_DEPLOYMENT` not set to `1`
- Startup Command not set to `startup.sh`

## Notes

- Update `app/metadata.py` if you want custom descriptions for each class.
- If your deployment provider has limited RAM, use a small CPU instance carefully because PyTorch can be heavy.
