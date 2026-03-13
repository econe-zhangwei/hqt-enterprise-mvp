import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { api } from '../../services/api';

const DEFAULT_FORM = {
  enterprise_name: '上海某科技有限公司',
  uscc: '913100000000000001',
  region_code: 'SH-PD',
  industry_code: 'C39',
  contact_name: '张三',
  contact_mobile: '13800138000',
  employee_scale: '50-99',
  revenue_range: '1000万-5000万',
  rd_ratio: '6',
  ip_count: '12',
  qualification_tags: '高新技术企业,创新型中小企业',
};

export default function Profile({
  enterpriseId,
  onSave,
  onMatch,
}: {
  enterpriseId: string | null;
  onSave: (id: string) => void;
  onMatch: () => void;
}) {
  const [formData, setFormData] = useState(DEFAULT_FORM);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!enterpriseId) {
      return;
    }

    let cancelled = false;
    api
      .getEnterpriseProfile(enterpriseId)
      .then((profile) => {
        if (cancelled) return;
        setFormData({
          enterprise_name: profile.enterprise_name,
          uscc: profile.uscc,
          region_code: profile.region_code,
          industry_code: profile.industry_code,
          contact_name: profile.contact_name,
          contact_mobile: profile.contact_mobile,
          employee_scale: profile.employee_scale || '',
          revenue_range: profile.revenue_range || '',
          rd_ratio: String(profile.rd_ratio ?? ''),
          ip_count: String(profile.ip_count ?? ''),
          qualification_tags: (profile.qualification_tags || []).join(','),
        });
      })
      .catch(() => {
        if (!cancelled) {
          setMessage('未能加载已保存的企业画像，可直接重新填写。');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [enterpriseId]);

  const handleChange = (e: any) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSave = async (alsoMatch: boolean) => {
    setIsLoading(true);
    setMessage('正在保存...');
    try {
      const payload = {
        ...formData,
        rd_ratio: Number(formData.rd_ratio || 0),
        ip_count: Number(formData.ip_count || 0),
        qualification_tags: formData.qualification_tags.split(',').map(s => s.trim()).filter(Boolean),
      };
      const res = await api.saveProfile(payload);
      onSave(res.enterprise_id);
      setMessage(`保存成功，企业ID：${res.enterprise_id}`);
      
      if (alsoMatch) {
        setMessage('保存成功，正在进入匹配页...');
        onMatch();
      }
    } catch (err: any) {
      setMessage(err.message || '保存失败');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1280px] space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>企业画像填写</CardTitle>
              <CardDescription>围绕基础信息、经营规模和创新能力建立企业画像。</CardDescription>
            </div>
            <span className="w-fit px-3 py-1 rounded-full bg-[#EEF4FA] text-[#1E3A5F] text-xs font-semibold border border-[#D4E0EC]">
              匹配输入
            </span>
          </div>
        </CardHeader>
        <CardContent className="space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Input label="企业名称" name="enterprise_name" value={formData.enterprise_name} onChange={handleChange} />
            <Input label="统一社会信用代码" name="uscc" value={formData.uscc} onChange={handleChange} />
            
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-slate-700">所在区域</label>
                  <select 
                    name="region_code" 
                    value={formData.region_code} 
                    onChange={handleChange}
                    className="flex h-11 sm:h-10 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-base sm:text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#1E3A5F]/15 focus:border-[#1E3A5F]"
                  >
                <option value="SH-ALL">全上海</option>
                <option value="SH-PD">浦东新区 SH-PD</option>
                <option value="SH-MH">闵行区 SH-MH</option>
              </select>
            </div>
            
            <Input label="行业代码" name="industry_code" value={formData.industry_code} onChange={handleChange} />
            <Input label="联系人" name="contact_name" value={formData.contact_name} onChange={handleChange} />
            <Input label="手机号" name="contact_mobile" value={formData.contact_mobile} onChange={handleChange} />
            
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-slate-700">员工规模</label>
                  <select 
                    name="employee_scale" 
                    value={formData.employee_scale} 
                    onChange={handleChange}
                    className="flex h-11 sm:h-10 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-base sm:text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#1E3A5F]/15 focus:border-[#1E3A5F]"
                  >
                <option value="10-49">10-49</option>
                <option value="50-99">50-99</option>
                <option value="100-299">100-299</option>
              </select>
            </div>
            
            <Input label="营收区间" name="revenue_range" value={formData.revenue_range} onChange={handleChange} />
            <Input label="研发占比(%)" type="number" name="rd_ratio" value={formData.rd_ratio} onChange={handleChange} />
            <Input label="知识产权数量" type="number" name="ip_count" value={formData.ip_count} onChange={handleChange} />
            
            <div className="md:col-span-2">
              <Input label="资质标签（逗号分隔）" name="qualification_tags" value={formData.qualification_tags} onChange={handleChange} />
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t border-slate-100">
            <Button onClick={() => handleSave(false)} isLoading={isLoading} className="flex-1 sm:flex-none">
              保存企业信息
            </Button>
            <Button onClick={() => handleSave(true)} variant="secondary" isLoading={isLoading} className="flex-1 sm:flex-none">
              保存并执行匹配
            </Button>
          </div>
          
          {message && (
            <div className="text-sm text-slate-500 bg-slate-50 p-3 rounded-xl border border-slate-100">
              {message}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
