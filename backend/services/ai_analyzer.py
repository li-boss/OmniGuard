import os
import logging

logger = logging.getLogger(__name__)

# Setup HuggingFace mirror for China
os.environ['HF_ENDPOINT'] = os.getenv('HF_ENDPOINT', 'https://hf-mirror.com')

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("Transformers not installed. AI analysis will use fallback mode.")


class AIAnalyzer:
    def __init__(self, model_name="Qwen/Qwen2-1.5B-Instruct"):
        self.model = None
        self.tokenizer = None
        self.generator = None
        
        if TRANSFORMERS_AVAILABLE:
            try:
                logger.info(f"Loading AI model: {model_name}")
                self.tokenizer = AutoTokenizer.from_pretrained(
                    model_name, 
                    trust_remote_code=True,
                    resume_download=True
                )
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    device_map="auto",
                    trust_remote_code=True
                )
                logger.info("AI model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load AI model: {e}, using fallback mode")
                self.model = None
                self.tokenizer = None
    
    def analyze(self, stats, alarms):
        """分析告警数据并生成分析报告和建议"""
        logger.info("Starting analysis...")
        
        # 直接使用备用分析方法（基于规则的分析）
        logger.info("Using rule-based analysis for faster response")
        return self._fallback_analyze(stats, alarms)
    
    def _build_prompt(self, stats, alarms):
        """构建提示词"""
        total = stats['total']
        
        type_stats = "\n".join([f"- {k}: {v}次" for k, v in stats['by_type'].items()])
        
        severity_stats = f"""
- 严重: {stats['critical_count']}次
- 高: {stats['high_count']}次
- 中: {stats['medium_count']}次
- 低: {stats['low_count']}次
"""
        
        alarm_details = []
        for alarm in alarms[:10]:
            alarm_type = getattr(alarm, 'alarm_type', '未知')
            description = getattr(alarm, 'description', '') or ''
            camera_id = getattr(alarm, 'camera_id', '未知')
            severity = getattr(alarm, 'severity', '中')
            alarm_details.append(f"- [{severity}] {alarm_type} @ {camera_id}: {description[:50] if description else '无描述'}")
        
        alarm_details_str = "\n".join(alarm_details) if alarm_details else "无详细告警"
        
        prompt = f"""你是一名校园安全分析专家。请根据以下告警数据进行分析并给出建议。

过去24小时告警统计：
- 总告警数：{total}次

按类型统计：
{type_stats}

按严重程度统计：
{severity_stats}

最近告警详情（前10条）：
{alarm_details_str}

请完成以下任务：
1. 分析当前校园安全状况（2-3条分析，需结合告警类型和详情）
2. 提出针对性的安全改进建议（2-3条建议）

请用以下格式回复：
【分析】
1. ...
2. ...

【建议】
1. ...
2. ...
"""
        return prompt
    
    def _generate(self, prompt):
        """生成文本"""
        logger.info("Starting AI text generation...")
        logger.info(f"Prompt length: {len(prompt)} characters")
        
        try:
            inputs = self.tokenizer(prompt, return_tensors="pt")
            logger.info(f"Tokenized input: {inputs['input_ids'].shape}")
            
            logger.info("Running model inference (this may take 10-30 seconds on CPU)...")
            
            # 优化推理参数，加快速度
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=256,  # 减少输出长度，加快速度
                temperature=0.7,
                top_p=0.9,
                top_k=50,  # 添加 top_k 限制，加快采样
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                num_beams=1,  # 不使用 beam search
                use_cache=True,  # 使用 KV cache 加速
            )
            
            logger.info("Decoding model output...")
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            result = response[len(prompt):]
            
            logger.info(f"AI generation completed. Output length: {len(result)} characters")
            return result
            
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            raise
    
    def _parse_response(self, response):
        """解析 AI 响应"""
        analysis = []
        suggestions = []
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if '【分析】' in line:
                current_section = 'analysis'
            elif '【建议】' in line:
                current_section = 'suggestions'
            elif line and current_section:
                if line.startswith(('1.', '2.', '3.', '4.', '5.')):
                    content = line.split('.', 1)[1].strip()
                    if current_section == 'analysis':
                        analysis.append(content)
                    else:
                        suggestions.append(content)
        
        if not analysis and not suggestions:
            return self._fallback_analyze_from_text(response)
        
        return {'analysis': analysis, 'suggestions': suggestions}
    
    def _fallback_analyze_from_text(self, text):
        """从文本中提取分析和建议"""
        analysis = ["AI 分析结果：请查看完整报告了解详情。"]
        suggestions = ["请根据告警情况采取相应的安全措施。"]
        return {'analysis': analysis, 'suggestions': suggestions}
    
    def _fallback_analyze(self, stats, alarms):
        """备用分析方法（基于规则的分析）"""
        analysis = []
        suggestions = []
        
        total = stats['total']
        if total == 0:
            analysis.append("过去24小时内未发生安全告警事件，校园整体安全状况良好。")
            suggestions.append("继续保持现有的安全监控措施，定期检查监控设备运行状态。")
            suggestions.append("建议定期开展安全演练，提高师生安全意识。")
        else:
            # 分析总体情况
            if stats['critical_count'] > 0:
                analysis.append(f"过去24小时内发生了{stats['critical_count']}次严重告警，需要重点关注和处理。")
            
            if stats['by_type']:
                sorted_types = sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True)
                main_types = sorted_types[:3]
                type_str = "、".join([f"{t[0]}({t[1]}次)" for t in main_types])
                analysis.append(f"告警类型分布：{type_str}。")
            
            if stats['by_severity']['high'] > 5:
                analysis.append("高等级告警数量较多，建议加强重点区域的监控力度。")
            
            # 通用建议
            suggestions.append("建议加强重点区域的巡逻频次，确保安全人员及时响应告警。")
            suggestions.append("定期检查和维护监控设备，确保监控系统稳定运行。")
            
            # 根据告警类型和数量给出具体建议
            if '围栏入侵告警' in stats['by_type']:
                count = stats['by_type']['围栏入侵告警']
                if count >= 5:
                    analysis.append(f"围栏入侵告警频发（{count}次），可能存在围栏防护薄弱区域。")
                    suggestions.append("围栏入侵告警频发，建议立即检查围栏完整性，对薄弱区域进行加固。")
                    suggestions.append("考虑增加围栏周边的监控摄像头密度，提高预警能力。")
                else:
                    suggestions.append(f"针对{count}次围栏入侵告警，建议检查围栏完整性，必要时加固防护设施。")
            
            if '陌生人告警' in stats['by_type']:
                count = stats['by_type']['陌生人告警']
                if count >= 5:
                    analysis.append(f"陌生人告警较多（{count}次），可能存在门禁管理漏洞。")
                    suggestions.append("陌生人告警频发，建议加强门禁管理，完善访客登记制度。")
                    suggestions.append("考虑在主要出入口增设人脸识别设备，提高识别准确率。")
                else:
                    suggestions.append(f"针对{count}次陌生人告警，建议加强门禁管理，完善访客登记制度。")
            
            if '人脸欺骗告警' in stats['by_type']:
                spoof_count = stats['by_type']['人脸欺骗告警']
                if spoof_count >= 3:
                    analysis.append(f"检测到{spoof_count}次人脸欺骗告警，可能存在有预谋的欺骗尝试。")
                    suggestions.append("人脸欺骗告警较多，建议立即检查活体检测功能是否正常启用。")
                    suggestions.append("考虑升级活体检测算法，增加3D人脸识别或红外检测。")
                    suggestions.append("建议对人脸欺骗告警发生区域加强人工核验，确保身份真实性。")
                else:
                    analysis.append(f"检测到{spoof_count}次人脸欺骗告警，可能存在使用照片或视频尝试通过人脸识别的情况。")
                    suggestions.append("针对人脸欺骗告警，建议检查活体检测功能是否正常启用。")
            
            if '异常活动告警' in stats['by_type']:
                abnormal_count = stats['by_type']['异常活动告警']
                analysis.append(f"检测到{abnormal_count}次异常活动告警，需要进一步分析具体类型。")
                suggestions.append("针对异常活动告警，建议查看告警详情，区分火情和跌倒等具体情况。")
            
            # 检查详细告警类型（带破折号的）
            fall_count = sum(v for k, v in stats['by_type'].items() if '跌倒' in k)
            if fall_count > 0:
                if fall_count >= 3:
                    analysis.append(f"检测到{fall_count}次跌倒告警，需高度关注人员安全，可能存在地面安全隐患。")
                    suggestions.append("跌倒告警频发，建议立即检查相关区域地面湿滑情况，增设防滑设施。")
                    suggestions.append("在跌倒高发区域增设警示标识和扶手，提高安全防护。")
                else:
                    analysis.append(f"检测到{fall_count}次跌倒告警，需关注人员安全，建议检查地面防滑措施。")
                    suggestions.append("针对跌倒告警，建议检查地面湿滑情况，增设防滑设施和警示标识。")
            
            fire_count = sum(v for k, v in stats['by_type'].items() if '火情' in k)
            if fire_count > 0:
                if fire_count >= 3:
                    analysis.append(f"检测到{fire_count}次火情告警，需立即排查火灾隐患，可能存在火灾风险。")
                    suggestions.append("火情告警频发，建议立即检查消防设施完好性，组织消防安全检查。")
                    suggestions.append("加强火灾隐患排查，重点关注电气设备和易燃物品存放区域。")
                    suggestions.append("建议开展消防安全培训，提高师生消防安全意识。")
                else:
                    analysis.append(f"检测到{fire_count}次火情告警，需立即排查火灾隐患。")
                    suggestions.append("针对火情告警，建议检查消防设施完好性，加强火灾隐患排查。")
        
        return {'analysis': analysis, 'suggestions': suggestions}