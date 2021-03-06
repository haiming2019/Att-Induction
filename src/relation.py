import torch
import torch.nn as nn
from torch.nn import functional as F


class RelationNetwork(nn.Module):
    def __init__(self, encoder, relation_module, hidden_size, max_length,
                 current_device=torch.device("cpu")):
        super(RelationNetwork, self).__init__()
        self.encoder = encoder
        self.relation_module = relation_module
        self.hidden_size = hidden_size  # D
        self.max_length = max_length
        self.current_device = current_device

    def loss(self, predict_proba, label):
        # MSE loss
        N = predict_proba.size(-1)
        label_one_hot = F.one_hot(label.type(torch.long), num_classes=N)
        return F.mse_loss(predict_proba.view(-1, N),
                          label_one_hot.view(-1, N).type(torch.float),
                          reduction="sum")
    
    def mean_accuracy(self, predict_label, label):
        return torch.mean((predict_label.view(-1) == label.view(-1)).type(torch.FloatTensor))

    def forward(self, support, support_mask, query, query_mask):
        """Relation Network forward.

        Args:
            support: torch.Tensor, [-1, N, K, max_length]
            support_mask: torch.Tensor, [-1, N, K, max_length]
            query: torch.Tensor, [-1, totalQ, max_length]
            query_mask: torch.Tensor, [-1, totalQ, max_length]
            
        Returns:
            relation_score: torch.Tensor, [B, totalQ, N]
            predict_label: torch.Tensor, [B, totalQ]"""
        B, N, K = support.size()[:3]
        totalQ = query.size()[1]  # Number of query instances for each batch
        
        # 1. Encoder
        support = support.view(-1, self.max_length)  # [B * N * K, max_length]
        support_mask = support_mask.view(-1, self.max_length)
        query = query.view(-1, self.max_length)  # [B * totalQ, max_length]
        query_mask = query_mask.view(-1, self.max_length)

        support = self.encoder(support, support_mask)  # [B * N * K, D]
        query = self.encoder(query, query_mask)  # [B * totalQ, D]
        support = support.view(-1, N, K, self.hidden_size)  # [B, N, K, D]
        query = query.view(-1, totalQ, self.hidden_size)  # [B, totalQ, D]

        # 2. Induction
        support = support.mean(2, keepdim=False)  # [B, N, D]

        # 3. Relation
        support = support.unsqueeze(1).expand(-1, totalQ, -1, -1)  # [B, totalQ, N, D]
        query = query.unsqueeze(2).expand(-1, -1, N, -1)  # [B, totalQ, N, D]
        relation_score = self.relation_module(support, query)  # [B, totalQ, N]

        predict_label = relation_score.argmax(dim=-1, keepdims=False)  # [B, totalQ]

        return relation_score, predict_label