//jSON交互部分是AI改的（不会JSON交互qwq)，参数是调优的，不用那么在意，看个思路就可以了(统计history写的有点混乱。（有些注释是AI加的
#include<bits/stdc++.h>
#include "jsoncpp/json.h"
using namespace std;
const double Chen_score[15]={0.00,0.00,1.00,1.50,2.00,2.50,3.00,3.50,4.00,4.50,5.00,6.00,7.00,8.00,10.00};
Json ::Value curReq;
int card_id(int card) { return card%4; } //花色
int card_number(int card) { return (int)(card/4+2) ; }  // 牌面 2-14  A=14
int next_paler(int Dealer,int tmp,int num) { return (Dealer+tmp)%num; }//计算谁下小盲注和大盲注,双人1为小盲注
struct Card
{
    int id;
    int number;
};
struct information_5
{
    double score=0.0;//初始化
    int type=0;//type牌型 1:同花顺，2：四条，3：葫芦，4：同花 5：顺子 6：三条 7：两对 8：一对 9：高牌
    int tkd=0,fkd=0;
    bool flush=0,straight=0,twopair=0,onepair=0;
    vector<int> pair,kicker;
};
bool is_basci_pair=0,is_public_flush=0,is_public_potential_straight=0; // 底牌对子 同花(>=3),顺子可能
int public_pair_cnt=0,public_tkd=0,public_fkd=0;//公牌对子数  三条  四条
vector<int> public_pair_rank;
double evaluate_2()//依据Chen简单计算牌力
{
    int rank[2],suit[2],tmpcnt=0;
    double tmpscore=0;
    for(auto &h : curReq["my_cards"])
    {
        int tmpnumber=h.asInt();
        rank[tmpcnt]=card_number(tmpnumber);
        suit[tmpcnt]=card_id(tmpnumber);
        tmpcnt++;
    }
    if(rank[0]<rank[1]) swap(rank[0],rank[1]);//0>1
    is_basci_pair=(rank[0]==rank[1]);//longrunning: 每手重新判定（原只在成对时置1，非对子沿用旧值会污染跨回合）
    if(rank[0]==rank[1]) tmpscore=max(4.96,2.48*Chen_score[rank[0]]);//对子（R2: 参数化）
    else //非对子
    {
        tmpscore=Chen_score[rank[0]]+Chen_score[rank[1]]/2;
        if(rank[0]==14 || rank[1]==14) tmpscore+=1.22;//有A高牌
        if(suit[0]==suit[1]) tmpscore+=2.05;//同花单牌
        else if(abs(rank[0]-rank[1])>=2) tmpscore-=1.83;//不同花且不相连
    }
    return tmpscore;
}
void check_public(vector<int> cards)//检查公共牌面情况
{
    is_basci_pair=is_public_flush=is_public_potential_straight=public_pair_cnt=0;
    public_pair_rank.clear();//longrunning: 清空上一手残留的公对点数
    public_tkd=0;//longrunning: 跨回合归零
    public_fkd=0;
    int n=cards.size();
    vector<int> rank(n),suit(n);
    map<int,int> cnt_rank,cnt_suit;
    for(int i=0;i<n;i++)
    {
        rank[i]=card_number(cards[i]);
        suit[i]=card_id(cards[i]);
        cnt_rank[rank[i]]++;
        cnt_suit[suit[i]]++;
    }
    for(int i=0;i<=3;i++) if(cnt_suit[i]>=3) is_public_flush=1;//同花可能
    for(auto &[r,c]:cnt_rank)
    {
    if(c==2) public_pair_cnt++,public_pair_rank.push_back(r);//对子
    else if(c==3) public_tkd=r;//三条
    else if(c==4) public_fkd=r;//四条
    }
    int l=1,r=1,tmple_cnt=0;//滑动区间判顺子 区间内有超过三张则有可能
    while(r<=14)
    {
        if(cnt_rank[r] || (r==1 && cnt_rank[14])) tmple_cnt++;// A:1,14
        if(r-l+1==5)
        {
            if(tmple_cnt>=3) is_public_potential_straight=1;
            if(cnt_rank[l] || (l==1 && cnt_rank[14])) tmple_cnt--;//移动左端点
            l++;
        }
        r++;
    }
}
double evaluate_context(information_5 cards,double odds)//纹理系数 听牌率
{
    double ans=cards.score;
    if(cards.type==9)//高牌
    {
        ans+=min(odds*100*0.91,57.19);
    }
    if(cards.type==8 )//一对
    {
       // 公共对子判断（最小化版）：仅处理"公对借用"——自己的对子点数=公共对子，
       // 且底牌无该点数（对子完全来自公牌，如拿 K8 用 board 的 7-7 凑对），仅剩踢脚比拼。
       // 不叠加 TX_PAIR_PP/顺面/花面全系数（R2 系数在 type 死代码前提下调的，全激活过度收紧）。
       // 公对越大，对手范围越容易压过自己，折价越狠。
       if(public_pair_cnt>=1 && !cards.pair.empty()){
           int mypair=cards.pair[0];
           bool in_board_pair=false;
           for(int pr: public_pair_rank) if(pr==mypair) { in_board_pair=true; break; }
           if(in_board_pair){
               bool have_in_hole=false;
               for(auto &h: curReq["my_cards"]) if(card_number(h.asInt())==mypair) have_in_hole=true;
               if(!have_in_hole)
                   ans*=(mypair>=12 ? 0.44 : mypair>=9 ? 0.52 : 0.60);//公对Q+ /9-T /2-8
           }
       }
    }
    else if(cards.type==7)//两对
    {
        if(public_pair_cnt==1) ans*=0.96;
        else if(public_pair_cnt==2) ans*=0.80;
        if(is_public_potential_straight) ans*=0.85;
        if(is_public_flush) ans*=0.82;
        ans+=min(odds*100*0.56,57.19);
    }
    else if(cards.type==6)//三条
    {
        if(public_pair_cnt==1) ans*=0.99;
        if(is_public_potential_straight) ans*=0.90;
        if(is_public_flush) ans*=0.87;
        if(cards.kicker[0]<cards.kicker[1]) swap(cards.kicker[0],cards.kicker[1]);//公共三条特殊处理  分段重新计算牌力
        if(cards.tkd==public_tkd) ans=(cards.kicker[0]<10.00 ? 30.00+(cards.kicker[0]-2)*1.00+(cards.kicker[1]-2)*0.20 : 70.00+(cards.kicker[0]-10.00)*3.00+(cards.kicker[1]-2)*0.50);
    }
    else if(cards.type==5)//顺子
    {
        if(public_pair_cnt==1) ans*=0.95;
        if(is_public_flush) ans*=0.93;
    }
    else if(cards.type==4)//同花
    {
        if(public_pair_cnt==1) ans*=0.93;
        if(is_public_flush) ans*=0.93;
    }
    return ans;
}
double evaluate_cluture(vector<int> cards,int round)//听牌（同花，顺子）成功率  多重听牌统计不重复的outs
{
    if(round==3) return 0.0;//河牌圈听牌无价值
    int n=4+round,total_outs=0,tmple_outs=0;
    double total_odds=0;
    vector<int> rank(n),suit(n);
    map<int,int> cnt_rank,cnt_suit;
    for(int i=0;i<n;i++)
    {
        rank[i]=card_number(cards[i]);
        suit[i]=card_id(cards[i]);
        cnt_rank[rank[i]]++;
        cnt_suit[suit[i]]++;
    }
    bool will_flush=0,is_flush_outs[15];//同花听牌 (只缺1张同花)
    for(int i=2;i<=14;i++) is_flush_outs[i]=1;//默认是
    int flush_suit=-1;//记录花色
    for(auto &[s,c] :cnt_suit) if(c==4) will_flush=1,flush_suit=s;//outs=9
    for(int i=0;i<n && will_flush;i++) if(suit[i]==flush_suit) is_flush_outs[rank[i]]=0;//标记已有的
    if(will_flush) total_outs+=9;

    bool will_straight=0;//顺子听牌（缺一张）
    sort(rank.begin(),rank.end());
    bool is_straight_outs[15];
    for(int i=0;i<=14;i++) is_straight_outs[i]=0;//默认不是
    for(int i=0;i<n;i++)//特殊情况    A 2 3 4 5 6 7
    {
        if(i+3<n && rank[i+3]-rank[i]==3)// 两头听顺   A 2,3,4,5...10 J Q K A
        {
            if(rank[i+3]==14 && !is_straight_outs[rank[i]-1])// j q k A
            {
                tmple_outs+=(is_flush_outs[rank[i]-1] && will_flush ? 3:4);//有同花标记则-1
                is_straight_outs[rank[i]-1]=1;//标记是顺子听牌
            }
            else if(rank[i]==2)// 2 3 4 5
            {   //有同花听牌且该牌是同花听牌才-1
                if(!is_straight_outs[14]) tmple_outs+=(is_flush_outs[14] && will_flush ? 3:4),is_straight_outs[14]=1;//缺A
                if(!is_straight_outs[6])  tmple_outs+=(is_flush_outs[6] && will_flush ? 3:4),is_straight_outs[6]=1;//缺6
            }
            else
            {
                if(!is_straight_outs[rank[i]-1]) tmple_outs+=(is_flush_outs[rank[i]-1] && will_flush ? 3:4),is_straight_outs[rank[i]-1]=1;
                if(!is_straight_outs[rank[i]+4]) tmple_outs+=(is_flush_outs[rank[i]+4] && will_flush ? 3:4),is_straight_outs[rank[i]+4]=1;
            }
        }
        if(i+4<n && rank[i+4]-rank[i]==4) will_straight=1;//有顺子
    }
    if(rank[n-1]==14 && rank[0]==2 && rank[1]==3 && rank[2]==4 && !is_straight_outs[5]) tmple_outs+=(is_flush_outs[5] && will_flush ? 3:4);// A 2 3 4 缺5
    if(rank[n-1]==14 && rank[0]==2 && rank[1]==3 && rank[2]==4 && rank[3]==5) will_straight=1;//A 2 3 4 5
    for(int i=3;i<=13 && !will_straight;i++)//不是顺子则枚举rank
    {
        if(is_straight_outs[i]) continue;//避免重复计算
        if(i>=4 && i<=12 && cnt_rank[i-2]>0 && cnt_rank[i-1]>0 && cnt_rank[i+1]>0 && cnt_rank[i+2]>0) tmple_outs+=(is_flush_outs[i] && will_flush ? 3:4);//卡顺分类
        else if(i>=5 && i<=13 && cnt_rank[i-3]>0 && cnt_rank[i-2]>0 && cnt_rank[i-1]>0 && cnt_rank[i+1]>0) tmple_outs+=(is_flush_outs[i] && will_flush? 3:4);
        else if(i>=3 && i<=11 && cnt_rank[i+3]>0 && cnt_rank[i+2]>0 && cnt_rank[i+1]>0 && cnt_rank[i-1]>0) tmple_outs+=(is_flush_outs[i] && will_flush? 3:4);
    }
    if(!will_straight) total_outs+=tmple_outs;
    if(round==1) total_odds=1.0-(47.0-total_outs)*(46.0-total_outs)/(46.0*47.0);//近似
    else total_odds=total_outs/46.0;
    return total_odds;
}
information_5 evaluate_5(vector<int> cards)
{
    //同花顺 100> 四条 99-99.6> 葫芦 95-97.4> 同花 90-94> 顺子 85.9-88.6> 三条 75-82.6> 两对 55.6-62.6> 对子 45-52.2> 高牌30.4-42.8
    information_5 ans;
    vector<int> rank(5),suit(5);
    map<int,int> cnt;
    for(int i=0;i<5;i++)
    {
        rank[i]=card_number(cards[i]);
        suit[i]=card_id(cards[i]);
        cnt[rank[i]]++;
    }
    ans.flush=1;//修复：原代码 flush 初始为 0 且循环从不置 1，导致同花/同花顺永远识别不了
    for(int i=1;i<5;i++)
    {
        if(suit[i]!=suit[0])
        {
            ans.flush=0;
            break;
        }
    }
    sort(rank.begin(),rank.end());//排序方便知道第几大
    int straight_high=0;
    if(cnt.size()==5)
    {
        if(rank[4]-rank[0]==4) ans.straight=1;
        else if(rank==vector<int>{2,3,4,5,14})// A 2 3 4 5
        {
            ans.straight=1;
            straight_high=5;
        }
    }
    for(auto &[r,c] :cnt)
    {
        if(c==4) { ans.fkd=r; }
        else if(c==3) { ans.tkd=r; }
        else if(c==2) ans.pair.push_back(r);
        else if(c==1) ans.kicker.push_back(r);
    }
    //计算牌型基础分（R2: S5_* 参数化）
    if(ans.flush && ans.straight) ans.score=100,ans.type=1;//同花顺
    else if(ans.fkd) ans.score=99.29+(ans.kicker[0]-2)*0.05, ans.type=2;
    else if(ans.tkd && ans.pair.size()) ans.score=97.82+(ans.tkd-2)*0.15+(ans.pair[0]-2)*0.05, ans.type=3;
    else if(ans.flush) ans.score=92.94+(rank[4]-2)*0.2+(rank[3]-2)*0.1+(rank[2]-2)*0.05, ans.type=4;
    else if(ans.straight)                              // 以上有时全压有时加注
    {
        if(straight_high==0) ans.score=81.91+(rank[4]-2)*0.3;
        else ans.score=81.91+(straight_high-2)*0.3;
        ans.type=5;
    }
    else if(ans.tkd && !ans.pair.size())
    {
        sort(ans.kicker.begin(),ans.kicker.end());
        ans.score=76.36+(ans.tkd-2)*0.5+(ans.kicker[1]-2)*0.1+(ans.kicker[0]-2)*0.05; ans.type=6;
    }
    else if(ans.pair.size()==2)// 加注，对手牌好或牌面湿可小额跟注
    {
        int mp=max(ans.pair[0],ans.pair[1]);
        int lp=min(ans.pair[0],ans.pair[1]);
        ans.score=61.62+(mp-2)*0.4+(lp-2)*0.2+ans.kicker[0]*0.05; ans.type=7;
    }
    else if(ans.pair.size()==1)//跟注，有时可加注（对手牌不好，牌面干）
    {
        ans.score=50.45+(ans.pair[0]-2)*0.6;
        ans.type=8;//修复：原代码未设置 type，导致 evaluate_context 中一对分支（公对借用折价）永不触发
    }
    else if(cnt.size()==5)  ans.score=37.03+(rank[4]-2)*0.8+(rank[3]-2)*0.2+(rank[2]-2)*0.1;//高牌 type 保持不设（最小化，避免激活听牌加分改变行为）
    return ans;
}
information_5 evaluate_n(vector<int> cards)//从n张牌中选5张
{
    int n=cards.size();
    information_5 ans;
    for(int i=0;i<n;i++)
    {
        for(int j=i+1;j<n;j++)
        {
            for(int k=j+1;k<n;k++)
            {
                for(int l=k+1;l<n;l++)
                {
                    for(int r=l+1;r<n;r++)
                    {
                        information_5 tmple_ans=evaluate_5(vector<int>{cards[i],cards[j],cards[k],cards[l],cards[r]});
                        if(tmple_ans.score>ans.score) ans=tmple_ans;
                    }
                }
            }
        }
    }
    return ans;
}
// ============================================================================
// 跨手对手统计 / 画像判定
//   派生指标：denom（投入分母）、VPIP、PFR（收缩估计）、call_rate、check_rate、allin_rate、conf。
//   check_oppoent_img() 画像码：0 冷启动 1 全压型 2 紧被动nit 3 跟注站 4 被动可预测 5 紧激进TAG 6 松激进LAG 7 未定型
// ============================================================================
struct oppoent_infomation
{
    int last_hand=-1;//上一次观测的 hand（新手检测）
    int last_hlen=0;//尾索引：本手已计入 history 的元素数
    int cur_hand_invested=0;//本手对手是否已有投入性动作（call/raise/allin）→ VPIP 分子标记
    long long hands_count=0;//①手数：自 hand0 起的累计手数（每手 +1，跳号手亦补计）
    long long calls_count=0;//②对手 call
    long long raises_count=0;//③对手 raise（含 allin）
    long long allins_count=0;//④对手 allin
    long long checks_count=0;//⑤对手 check（单列）
    long long sb_folds_count=0;//⑥对手小盲位直接弃牌（跳号补计；唯一可回收的弃牌信号）
    long long invest_hands=0;//有投入性动作的手数（VPIP 分子）
    double denom=0;//投入分母=calls_count+raises_count（allin 已含在 raises_count 内，勿再加 allins_count）
    double VPIP=0;//有投入动作的手数
    double PFR=0;//加注
    double call_rate=0;//calls_count/denom
    double check_rate=0;//checks_count/(denom+checks_count)
    double allin_rate=0;//allins_count/denom
    double conf=0;//置信度：hands<3 → 0；3~9 → 0.3+0.1*(hands-3)；>=10 → 1
    int img_stable=0;//稳定画像（防抖后的生效画像；0=冷启动 → 决策偏移全 0）
    int img_pending=-1;//待确认画像（防抖用）
    int img_pending_cnt=0;//待确认画像的连续出现次数
    double d_call=0;//决策偏移：跟注门槛乘性系数（th*=(1+d_call)）
    double d_allin_call=0;//决策偏移：跟全压门槛乘性系数
    double d_raise=0;//决策偏移：加注门槛乘性系数
    double d_size=0;//决策偏移：加注尺寸乘性系数
    double d_bluff=0;//决策偏移：诈唬门槛乘性系数（正=少诈唬，负=多诈唬）
    double d_cheap_min=0;//决策偏移：小注看牌的绝对牌力门槛（0=不限）
    void observe(int hand,const Json::Value &hist,int my_id,int dealer_id)
    {
        if(hand<last_hand)//手号回退=新开一场，全量归零
        {
            last_hand=-1; last_hlen=0; cur_hand_invested=0;
            hands_count=calls_count=raises_count=allins_count=checks_count=sb_folds_count=invest_hands=0;
            img_stable=0; img_pending=-1; img_pending_cnt=0;//换场：画像决策状态一并归零
        }
        if(last_hand<0 && hand==1 && dealer_id==my_id)//首个观测点为 hand1 且我方为小盲
        {
            //dealer=小盲逐手交替、我方小盲必被询问 → hand0 未被观测只可能是对手小盲位弃牌
            hands_count++; sb_folds_count++;
        }
        if(last_hand>=0 && hand>last_hand+1)//跳号 = 对手小盲位弃牌（我方大盲未被询问）
        {
            long long skipped=hand-last_hand-1;//区间内未被观测的手 = 对手小盲位弃牌的手
            if(skipped<1) skipped=1;//dealer 逐手交替且我方小盲必被询问 → 理论恒为 1
            hands_count+=skipped; sb_folds_count+=skipped;
        }
        if(hand!=last_hand)//换手：手数 +1、本手投入标记清零、尾索引归零
        {
            hands_count++; last_hand=hand; last_hlen=0; cur_hand_invested=0;
        }
        int n=(int)hist.size();
        if(n<last_hlen) last_hlen=n;//异常保护：history 回退时不重复计数
        for(int i=last_hlen;i<n;i++)//只处理本手新追加的元素 → 天然不重复计数
        {
            const Json::Value &h=hist[i];
            if(h["player_id"].asInt()==my_id) continue;//只统计对手
            string t=h["action_type"].asString();
            if(t=="raise") raises_count++;
            else if(t=="allin"){ allins_count++; raises_count++; }//allin 计入 raises
            else if(t=="call") calls_count++;
            else if(t=="check"){ checks_count++; continue; }//check 单列，不计入 VPIP
            else continue;//fold/未知类型不计
            if(!cur_hand_invested){ cur_hand_invested=1; invest_hands++; }//本手首次投入 → VPIP 分子 +1
        }
        last_hlen=n;
        calc();//刷新派生指标（denom/VPIP/PFR/各率/conf）
    }
    void calc()//按计数项刷新派生指标
    {
        denom=(double)(calls_count+raises_count);//allin 已含在 raises_count 内，勿再加 allins_count
        VPIP=(hands_count>0 ? (double)invest_hands/(double)hands_count : 0.0);
        call_rate=(denom>0 ? (double)calls_count/denom : 0.0);
        check_rate=((denom+(double)checks_count)>0 ? (double)checks_count/(denom+(double)checks_count) : 0.0);
        allin_rate=(denom>0 ? (double)allins_count/denom : 0.0);
        PFR=((double)raises_count+5*0.30)/(denom+5);//
        if(hands_count>=10) conf=1.0;
        else if(hands_count>=3) conf=0.3+0.1*(hands_count-3);
        else conf=0.0;
        update_img();//刷新画像决策偏移量（含防抖）
    }
    int check_oppoent_img()//对手画像判定：0 冷启动/1 全压型/2 紧被动nit/3 跟注站/4 被动可预测/5 紧激进TAG/6 松激进LAG/7 未定型
    {
        if(conf<1.0 || denom<20) return 0;//样本不足 → 冷启动：调用方应退回无对手适配基线
        if(allin_rate>0.05) return 1;//全压型优先覆盖其余画像（同一动作在两类对手下含义相反），必须跑在 nit 之前
        if(PFR<0.12) return 2;//紧被动：小注=价值注、大注/全压=超强 → 收紧
        if(PFR<0.15 && call_rate>=0.60) return 3;//跟注站：弃牌率≈0 → 停止诈唬、价值注打满
        if(call_rate>=0.35 && call_rate<0.60 && PFR<=0.30) return 4;//被动可预测
        if(VPIP<0.45 && PFR>=0.25 && PFR<=0.60) return 5;//紧激进：尊重其加注 → 跟注收窄
        if(VPIP>0.55 && PFR>0.30) return 6;//松激进：范围含大量空气 → 放宽跟注、中等牌力抓诈
        return 7;//未定型
    }
    void update_img()//画像决策：防抖 + 生成决策偏移量（冷启动/未定型 → 全 0 = 无适配基线）
    {
        int now=check_oppoent_img();
        if(now==img_pending) img_pending_cnt++;
        else { img_pending=now; img_pending_cnt=1; }
        if(img_pending_cnt>=2) img_stable=img_pending;//连续 2 手同画像才切换（防抖）
        d_call=d_allin_call=d_raise=d_size=d_bluff=d_cheap_min=0.0;
        if(img_stable==1){ d_call=-0.10; d_allin_call=-0.25; d_raise=0.20; d_size=-0.10; d_bluff=0.20; }//全压型：范围宽→放宽跟注、少加注、控池
        else if(img_stable==2){ d_call=0.15; d_allin_call=0.20; d_raise=0.15; d_size=-0.15; d_bluff=-0.15; d_cheap_min=50.0; }//紧被动nit：其小注=价值注、全压=超强→收紧；弃牌率高→可多诈唬
        else if(img_stable==3){ d_call=0.15; d_allin_call=0.15; d_raise=-0.20; d_size=0.20; d_bluff=0.20; d_cheap_min=50.0; }//跟注站：弃牌率≈0→停止诈唬、价值注打满
        else if(img_stable==4){ d_call=0.10; d_allin_call=0.10; d_raise=-0.10; d_size=0.10; d_bluff=0.10; d_cheap_min=25.0; }//被动可预测：弱化版跟注站
        else if(img_stable==5){ d_call=0.10; d_allin_call=0.15; d_raise=0.0; d_size=0.0; d_bluff=0.10; d_cheap_min=25.0; }//紧激进TAG：尊重其加注→跟注收窄
        else if(img_stable==6){ d_call=-0.15; d_allin_call=-0.20; d_raise=0.0; d_size=-0.15; d_bluff=0.20; }//松激进LAG：范围含大量空气→放宽跟注、控池、少诈唬
        d_call*=conf; d_allin_call*=conf; d_raise*=conf; d_size*=conf; d_bluff*=conf; d_cheap_min*=conf;//按置信度渐进生效
    }
};
int main()
{
    //随机数
    std::random_device rd;
    std::mt19937 gen(rd());
    Json::Reader reader;
    string str;
    //跨手对手统计/画像实例：声明在 while 之外 → 整个进程（一场约 50 手）常驻
    oppoent_infomation oppoent_info;
    bool first_turn=true;
    while(getline(cin,str))//longrunning: 每决策读一行；EOF(场终 TerminateProcess)退出
    {
        Json::Value input;
        if(!reader.parse(str,input)) break;
        // —— 兼容两种输入格式 ——
        if(input.isMember("requests") && input["requests"].size()>0)//traditional 首信封/完整历史
        {
            int turnID=input["requests"].size()-1;
            if(input["requests"][turnID].isString()) reader.parse(input["requests"][turnID].asString(),curReq);
            else curReq=input["requests"][turnID];
        }
        else if(input.isMember("request"))//longrunning 后续回合：单条增量信封
        {
            if(input["request"].isString()) reader.parse(input["request"].asString(),curReq);
            else curReq=input["request"];
        }
        else break;//未知格式
    //读取request
    int my_chips=curReq["my_chips"].asInt();   //剩余筹码数
    int dealer_id=curReq["dealer_id"].asInt();//庄家id 一开始下bb(大盲位)
    int my_id=curReq["my_id"].asInt();//我的id
    int hand=curReq["hand"].asInt();//当前局数
    int max_hand=curReq["max_hand"].asInt();//总局数
    int total_win_chips=curReq["total_win_chips"][my_id].asInt();//累积净赢筹码
    //check game_over（锁胜：剩余局数即使全输也追不上 → 弃牌保胜）
    bool is_game_over=0;
    int tmple_bet=(my_id==dealer_id ? 50 : 100);//BotBattle: dealer=按钮=小盲(50)，非dealer=大盲(100)
    if(total_win_chips>(int)((max_hand-hand+1)/2)*150+tmple_bet) is_game_over=1;
    int round=0; // 0:preflop 1:flop 2:turn 3:river
    int round_bet=100;//本轮最大下注数
    int round_raise=0;//最小加注增量(delta)
    int last_inc=0;//最小加注增量基（每街重置）
    int round_action_count=0;//本轮叫注次数
    int pot_chips=150;//底池筹码
    // 玩家返回的response，-1: fold，-2: allin，0: call/check，>0:raise
    // 玩家操作的类型，["fold", "allin", "call", "check", "raise"]中的一种
    int ans_action=0;//最终决策

    int player_bet[2];//
    player_bet[dealer_id]=50;//BotBattle: dealer=按钮=小盲先下50
    player_bet[1-dealer_id]=100;//非dealer=大盲下100

    int oppoent_raise_count=0;//对手加注次数
    int oppoent_check_count=0;//对手check次数
    int oppoent_put_chips=(dealer_id==my_id ? 100 : 50);//BotBattle: 我=dealer(小盲)时对手=大盲(100)
    bool h_has_round=false;//history 元素是否携带 round 字段；有 → 显式切街，无 → 退回 call/check 
    if(curReq["history"].isArray() && !curReq["history"].empty())
        h_has_round=curReq["history"][0].isMember("round");
    for(auto &h: curReq["history"])
    {
        
        if(h_has_round)
        {
            int cur_r=h["round"].asInt();
            if(cur_r!=round)//引擎街号前进 → 街切换（street 清零、last_inc 重置）
            {
                round=cur_r; round_bet=0; round_action_count=0; last_inc=0;
                player_bet[0]=player_bet[1]=0;
            }
        }
        //int cur_round=h["round"].asInt();
        int player_id=h["player_id"].asInt();
        int cur_action=h["action"].asInt();
        string type=h["action_type"].asString();
        if(type=="allin")
        {
            round_bet=-2;//标记全压
            player_bet[player_id]=-2;
        }
        else if(type=="raise")
        {
            if(player_id!=my_id) oppoent_put_chips+=cur_action,oppoent_raise_count++;
            int old_max=round_bet;
            int prev=player_bet[player_id]; if(prev<0) prev=0;//全压哨兵保护
            player_bet[player_id]=prev+cur_action;          // 增量累加（action 是 delta 非总额）
            if(player_bet[player_id]>round_bet) round_bet=player_bet[player_id];
            int inc=player_bet[player_id]-old_max;          // 本次加注增量
            if(inc>0 && (last_inc==0 || inc>=last_inc)) last_inc=inc;
            round_action_count++;
            pot_chips+=cur_action;                         // 
        }
        else if(type=="call" || type=="check")
        {
            int delta=round_bet-player_bet[player_id];//本轮需补齐的增量
            if(delta<0) delta=0;
            player_bet[player_id]=round_bet;
            round_action_count++;
            pot_chips+=delta;//加进底池
             if(player_id!=my_id) oppoent_put_chips+=delta;
            if(type=="check" && player_id!=my_id) oppoent_check_count++;
            int tmpcount=0;
            for(int i=0;i<=1;i++) if(player_bet[i]>=0) tmpcount++;
            if(!h_has_round && round_action_count>=tmpcount && player_bet[1-player_id]==round_bet)//判断进入下一轮（仅 history 无 round 字段时启用的 fallback）
            {
                round++;
                round_bet=0;//重置当前轮次最大下注
                round_action_count=0;
                last_inc=0;//每街重置最小加注增量
                player_bet[0]=player_bet[1]=0;
            }
        }
    }
    //重置
    {
        int pcnt=(int)curReq["public_cards"].size();
        int pc_round=(pcnt>=5)?3:(pcnt>=4)?2:(pcnt>=3)?1:0;
        if(pc_round>round)//街号只前进；同街中段 pc_round==round → 保留 rb/pb 状态
        {
            round=pc_round; round_bet=0; round_action_count=0; last_inc=0;
            player_bet[0]=player_bet[1]=0;
        }
    }
    // —— 决策前：按规则计算最小加注【增量】round_raise（最小加注按目标总额校验） ——
    {
        int inc_base=(last_inc>0 ? last_inc : 100);
        int to_call=round_bet-player_bet[my_id]; if(to_call<0) to_call=0;
        round_raise=to_call+inc_base;
    }
    // —— 跨手统计更新
    oppoent_info.observe(hand, curReq["history"], my_id, dealer_id);
    //决策部分
    double oppoent_chips_odds=(double)oppoent_put_chips/(double)pot_chips;//对手下注数占底池的比例
    double pot_odds;//底池赔率
    if(round==0)//翻牌前
    {
        double score_2=evaluate_2();//Chen分数
        bool flag=1;
        std::uniform_real_distribution<double> dist(0.0,max(0.0,(score_2-7.00)*0.16)),bluff_random(0.0,1.0);
        double random_pot_odds=dist(gen),random_bluff_odds=bluff_random(gen);//随机加注比例 随机bluff
        if(round_bet==-2)//翻牌前对手全压   全压后直接摊牌
        {
            double th_pre_allin=17.16*(1.0+oppoent_info.d_allin_call);//画像：其全压范围宽度→跟全压门槛
            if(score_2>=th_pre_allin || (is_basci_pair && score_2>=15.00*(1.0+oppoent_info.d_allin_call))) ans_action=-2;
            else ans_action=-1;
            flag=0;
        }
        pot_odds=(double)(round_bet-player_bet[my_id])/(double)(round_bet-player_bet[my_id]+pot_chips);//跟注情况下的底池赔率
        double win_odds=(is_basci_pair ? 30.00+2.23*score_2+0.03*score_2*score_2 : 30.00+2.60*score_2);//分类估算胜率
        double d_bluff_up=(oppoent_info.d_bluff>0 ? oppoent_info.d_bluff : 0.0);//安全约束：翻前全压诈唬只允许收紧、不允许放宽（风险收益比≈133:1）
        if(flag && (score_2>=13.65*(1.0+d_bluff_up) ||(is_basci_pair && score_2>=9.50*(1.0+d_bluff_up) && random_bluff_odds<=0.10)))  ans_action=-2;// bluff
        else if((score_2>=13.35*(1.0+oppoent_info.d_raise) || (is_basci_pair && score_2>=7.57*(1.0+oppoent_info.d_raise))) && flag) //加注
        {
            //0-2
            double pre_size_k=1.0+oppoent_info.d_size;//画像：加注尺寸（nit 其注=价值→收小；station→打满）
            if(my_chips>=max(round_raise*1.0,pot_chips*((score_2-8)*0.32*pre_size_k+random_pot_odds))) ans_action=max(round_raise*1.0,pot_chips*((score_2-8)*0.32*pre_size_k+random_pot_odds));
            else if(my_chips>=round_raise) ans_action=round_raise;
            else ans_action=-2;//筹码不足则全压
        }
        else if(round_bet==0) ans_action=0;//牌不好能看牌就看牌
        else if(score_2>=3.00*(1.0+oppoent_info.d_call) && flag && win_odds+0.06>=pot_odds) //降低弃牌率 增加跟注判断
        {
            if(my_chips>=round_bet) ans_action=0;
            else ans_action=-2;//筹码不足则全压
        }
        else if(flag) ans_action=-1;
    }
    else
    {
        vector<int> public_cards,cards;
        for(auto &h: curReq["my_cards"]) cards.push_back(h.asInt());
        for(auto &h: curReq["public_cards"]) cards.push_back(h.asInt()),public_cards.push_back(h.asInt());
        check_public(public_cards);//看干湿
        double potential_odds=evaluate_cluture(cards,round);//听牌率
        information_5 ans=evaluate_n(cards);//得到牌型等信息
        double score=evaluate_context(ans,potential_odds);
        double base=evaluate_context(ans,0.0);//基础牌力（无听牌加分）——allin 判定用，防止听牌加分虚高触发全压
        bool flag=1;
        if(round_bet==-2)//对手全压
        {
            double th=(63.00+round*1.67)*(1.0+oppoent_info.d_allin_call);//画像：其全压范围宽度→跟全压门槛
            // 跟全压同样要求基础牌力（成牌）达标，避免听牌加分虚高误跟
            if(score>=th && base>=th) ans_action=-2;
            else ans_action=-1;
            flag=0;
        }
        pot_odds=(double)(round_bet-player_bet[my_id])/(double)(round_bet-player_bet[my_id]+pot_chips);//底池赔率
        // 主动全压：score 与 base（成牌）都达标才全压——听牌（potential_odds 加分虚高）不触发 allin
        double th_ai=94.00*(1.0+oppoent_info.d_raise);//画像：对 nit 收紧、对 station 放宽
        if(score>=th_ai && base>=th_ai && flag) ans_action=-2; // 强牌全压（score/base 双达标风控保留）
        else if(score>=(56.00+(round-1+oppoent_raise_count-oppoent_check_count)*1.20)*(1.0+oppoent_info.d_raise) && flag) // 对手加注多 少加注 对手check多 多加注bluff
        {
            std::uniform_real_distribution<double> dist(0.0,(score-51.51)*0.00);
            double random_pot_odds=dist(gen);//随机加注比例
            double tmple_basic_odds=(score<75.00 ? 0.75+(score-56.00)*0.03 : 0.75+(score-70)*0.15)*(1.0+oppoent_info.d_size);//底池比例（含画像尺寸调整）
            double tmple_round_raise=max(round_raise*1.0,pot_chips*(tmple_basic_odds+random_pot_odds));
            if(my_chips>=tmple_round_raise) ans_action=tmple_round_raise;
            else if(my_chips>=round_raise) ans_action=round_raise;
            else ans_action=-2;
        }
        else if(round_bet<=140.77 && flag && score>=oppoent_info.d_cheap_min) ans_action=0;//小成本看牌（画像门控：其小注=价值注时弱牌不免费看）
        else if(score>=(34.00+6.00*oppoent_chips_odds)*(1.0+oppoent_info.d_call) && flag && score+4.88>=pot_odds*100) //+5激进 score估算胜率 scoer上调
        {
            if(my_chips>=round_bet) ans_action=0;
            else ans_action=-2;
        }
        else if(flag) ans_action=-1;
    }
    if(is_game_over) ans_action=-1;//已锁定胜局 → 弃牌保胜
        Json::Value ret;
        ret["response"]=ans_action;
        Json::FastWriter writer;
        cout<<writer.write(ret);//FastWriter 自带 '\n'；勿再加 endl，否则多出空行使引擎把空行当握手行
        if(first_turn)//首响应后输出握手=常驻信号；traditional 模式引擎只读首行即丢弃，无害→同一二进制兼容两模式
        {
            cout<<">>>BOTZONE_REQUEST_KEEP_RUNNING<<<"<<endl;
            first_turn=false;
        }
        cout.flush();
    }
    return 0;
}
