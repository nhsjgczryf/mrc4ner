"""
这个文件的作用就是定义模型，然后在其他文件里面导入
"""
import torch
import torch.nn as nn
from transformers import *

class MyModel(nn.Module):
    def __init__(self, config):
        self.super(MyModel, self).__init__()
        self.config = config
        self.encoder = AutoModel.from_pretrained(config.pretrained_model_name_or_path)
        self.start_linear = nn.Linear(config.hiden_dim, 2)
        self.end_linear = nn.Linear(config.hiden_dim, 2)
        self.m = nn.Linear(2*config.hiden_dim, 1)

    def forward(self, input, mask):
        _, rep = self.encoder(input)
        start_logits = self.start_linear(rep)
        end_logits = self.end_linear(rep)
        #得到一个batch里面的Istart 和Iend
        start_idxs = []
        end_idxs = []
        for i in range(start_logits.shape[0]):
            start_idx = []
            end_idx = []
            for j in range(start_logits.shape[1]):
                if mask[i][j]!=0:
                    if start_logits[i][j][0]<=start_logits[i][j][1]:
                        start_idx.append(j)
                    if end_logits[i][j][0]<=end_logits[i][j][1]:
                        end_idx.append(j)
            start_idxs.append(start_idx)
            end_idxs.append(end_idx)
        spans = []
        for i in range(input.shape[0]):
            start_idx = start_idxs[i]
            end_idx = end_idxs[i]
            sps = []
            for s in start_idx:
                for e in end_idx:
                    if s<=e and self.m(torch.cat([start_logits[i][s],end_logits[i][e]]))>0 :
                        sps.append((s,e))
            spans.append(sps)
        return spans

    def loss(self, input, mask, start_target, end_target, spans):
        '''
        :param input: (batch,max_len)
        :param mask: (batch,max_len)
        :param start_target: (N) 所有元素均有效
        :param end_target: (N) 所有元素均有效
        :param spans:
        :return:
        '''
        #spans是[[(s1,e1),(s2,e2)],[(s3,e3),(s4,e4)]]
        _, rep = self.encoder(input)
        start_logits = self.start_linear(rep)
        end_logits = self.end_linear(rep)
        start_logits = torch.cat([start_logits[i].masked_select(mask[i])] for i in range(len(start_logits)))
        end_logits = torch.cat([end_logits[i].masked_select(mask[i])] for i in range(len(end_logits)))
        loss_start = nn.functional.cross_entropy(start_logits, start_target)
        loss_end = nn.functional.cross_entropy(end_logits, end_target)
        loss_span = []
        for i, sps in enumerate(spans):
            for s,e in sps:
                t = self.m(torch.cat((start_logits[i][s],end_logits[i][e])))
                l = nn.functional.binary_cross_entropy_with_logits(t)
                loss_span.append(l)
        loss_span = sum(loss_span)
        loss = self.config.alpha*loss_start+self.config.beta*loss_end+self.config.gamma*loss_span
        return loss