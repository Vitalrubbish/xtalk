# X-Talk
<img width="460" height="249" alt="xtalk-logo-new" src="https://github.com/user-attachments/assets/4e252ce8-7450-4335-b86a-4b9b26200792" />

[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen?style=for-the-badge)](https://xtalk.sjtuxlance.com/)
[![Docs](https://img.shields.io/badge/Documentation-Available-green?style=for-the-badge)](https://xtalk.readthedocs.io/)
[![arXiv](https://img.shields.io/badge/arXiv-Tech_Report-B31B1B?style=for-the-badge&logo=arxiv&logoColor=white)](https://arxiv.org/abs/2512.18706)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue?style=for-the-badge&labelColor=555555)](https://opensource.org/licenses/Apache-2.0)


<!-- <img src="PENDING" alt="Watermark" style="width: 40px; height: auto"> -->
> ⚠️ X-Talk is in active prototyping. Interfaces and functions are subject to change. We will try to keep interfaces stable.

X-Talk is an open-source full-duplex cascaded spoken dialogue system framework featuring:
- ⚡ **Low-Latency, Interruptible, Human-Like Speech Interaction**
    - Speech flow is optimized to support **impressive low latency**
    - Enables **natural user interruption** during interaction
    - **Paralinguistic information** (e.g. environment noise, emotion) is encoded in parallel to support in-depth understanding and empathy
- 🧪 **Researcher Friendly**
    - **New models and relevant logic** can be added [within one Python script](#introduce-a-new-model), and seamlessly integrated with the default pipeline.
- 🧩 **Super Lightweight**
    - The framework backend is **pure Python**; nothing to build and install beyond `pip install`.
- 🏭 **Production Ready**
    - **Concurrency** is ensured through asynchronous backend
    - Websocket-based implementation empowers deployment **from web browsers to edge devices**.
## 📚 Contents

- [Demo](#demo)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [Docs](#docs)
- [Contributing](#contributing)
- [Acknowledgements](#acknowledgements)
- [License](#license)

<a id="demo"></a>
## 🎬 Demo

### Online Demo
[Demo Link](https://xtalk.sjtuxlance.com/)

This demo runs on 4090 cluster with 8-bit quantized *SenseVoice* as speech recognizer, *IndexTTS 1.5* as speech generator, and 4-bit quantized *Qwen3-30B-A3B* as language model. Though at the cost of intelligence due to a relatively small language model, it demonstrates low latency.

### Demo Videos
<table class="center">
<tr>
    <td width=50% style="border: none">
        <video controls autoplay loop src="https://github.com/user-attachments/assets/e7946357-cd83-493c-8967-354cf87b2acb" muted="false"></video>
    </td>
    <td width=50% style="border: none">
        <video controls autoplay loop src="https://github.com/user-attachments/assets/ca45c463-6738-4b5c-8305-71fce4ab490e" muted="false"></video>
    </td>
</tr>
<tr>
    <td width=50% style="border: none">
        <video controls autoplay loop src="https://github.com/user-attachments/assets/8c0f489a-6af6-4711-a28c-7a48740f666c" muted="false"></video>
    </td>
    <td width=50% style="border: none">
        <video controls autoplay loop src="https://github.com/user-attachments/assets/d8fc4d15-edfb-4476-a9d3-983a1ce9be0e" muted="false"></video>
    </td>
</tr>
<tr>
    <td width=50% style="border: none">
        <video controls autoplay loop src="https://github.com/user-attachments/assets/7ea4dc44-d43c-45ca-8788-2032b3a387d8" muted="false"></video>
    </td>
    <td width=50% style="border: none">
        <video controls autoplay loop src="https://github.com/user-attachments/assets/9f296d5e-a752-435e-91a2-a9f1a71f9fac" muted="false"></video>
    </td>
</tr>
<tr>
    <td width=50% style="border: none">
        <video controls autoplay loop src="https://github.com/user-attachments/assets/2b44f2f1-93c4-47b8-99e0-830338cdba02" muted="false"></video>
    </td>
    <td width=50% style="border: none">
        <video controls autoplay loop src="https://github.com/user-attachments/assets/c4cd4c1b-c4fd-493b-8cb2-347c48ac5809" muted="false"></video>
    </td>
</tr>
<tr>
    <td width=50% style="border: none">
        <video controls autoplay loop src="https://github.com/user-attachments/assets/d33ca5ef-c722-45a6-93df-2fdb7ffcc729" muted="false"></video>
    </td>
    <td width=50% style="border: none">
        <video controls autoplay loop src="https://github.com/user-attachments/assets/09370641-7a26-4f93-9c98-dee887612fda" muted="false"></video>
    </td>
</tr>
</table>

The tour guiding demos are conducted with *Qwen3-Next-80B-A3B-Instruct* as language model, and the other eight demos are aligned with the online demo setting. Larger language models are more intelligent at the cost of latency.

<a id="installation"></a>
## 🛠️ Installation

```bash
pip install git+https://github.com/xcc-zach/xtalk.git@main
```

<a id="quickstart"></a>
## 🚀 Quickstart

We will use APIs from AliCloud to demonstrate the basic capability of **X-Talk**.

First, install dependencies for AliCloud and server script:
```bash
pip install "xtalk[ali] @ git+https://github.com/xcc-zach/xtalk.git@main"
pip install jinja2 python-multipart 'uvicorn[standard]'
```

Then, obtain an API key from [AliCloud Bailian Platform](https://bailian.console.aliyun.com/?tab=model#/api-key). We will be using free-tier service (currently) from AliCloud.

> Online service may be unstable and of high latency. We recommend using locally deployed models for better user experience. See [server config tutorial](https://xtalk.readthedocs.io/tutorial/config_the_service/) and [local deployment recipe](https://xtalk.readthedocs.io/tutorial/sample_config_for_fully_local_deployment/) for details.

After that, create a JSON config specifying the models to use, and **fill in <API_KEY>** with the key you obtained:

```json
{
    "asr": {
        "type": "Qwen3ASRFlashRealtime",
        "params": {
            "api_key": "<API_KEY>"
        }
    },
    "llm_agent": {
        "type": "DefaultAgent",
        "params": {
            "model": {
                "api_key": "<API_KEY>",
                "model": "qwen-plus-2025-12-01",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
            }
        }
    },
    "tts": {
        "type": "CosyVoice",
        "params": {
            "api_key": "<API_KEY>"
        }
    }
}
```

The next step is to compose the startup script. Since we also need to link frontend webpage and scripts to get the demo working, the startup script is ready at `examples/sample_app/configurable_server.py`. We simply need to start the server with the config file (**fill in <PATH_TO_CONFIG>.json** with the path to the config file we just created) and a custom port:
```bash
git clone https://github.com/xcc-zach/xtalk.git
cd xtalk
python examples/sample_app/configurable_server.py  --port 7635 --config <PATH_TO_CONFIG>.json
```

Finally, our demo is ready at `http://localhost:7635`. View it in the browser!

<a id="docs"></a>
## 📕 Docs

Docs [here](https://xtalk.readthedocs.io/)

## Contributing
    
See [Contribution Guide](CONTRIBUTING.md)

## Acknowledgements

We express sincere gratitude for:

- [Langchain](https://www.langchain.com/) as backbone of LLM agents
- [vllm](https://github.com/vllm-project/vllm) for deployment of most models
- All model providers mentioned in [Supported Models](#supported-models)

All of you provide the solid foundation of X-Talk!

## License
    
This project is licensed under the Apache License 2.0, if you do not install optional dependencies. Some optional dependencies may be under incompatible licenses.
